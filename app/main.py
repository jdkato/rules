import io
import pathlib
import re
import subprocess
import tempfile
import json

import streamlit as st
import pandas as pd
import yaml
import ruamel.yaml

from st_aggrid import AgGrid, GridOptionsBuilder
from streamlit_ace import st_ace

HTML_WRAPPER = """<div style="overflow-x: auto; line-height: 1 !important; border: 1px solid #e6e9ef; border-radius: 0.25rem; padding: 1rem; margin-bottom: 2.5rem">{}</div>"""


STYLES = pathlib.Path("testdata/styles")
RE_DESC = r"(.+)\n\ncategory: (.+)\n\nexample:\n\n(.*)"


def lint(example, rule):
    """Run Vale on the given example."""
    config = pathlib.Path("testdata") / rule["extends"] / ".vale.ini"
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w") as t:
        t.write(example)
        t.seek(0)
        return subprocess.check_output(
            [
                "bin/linux/vale",
                "--no-exit",
                "--output=JSON",
                f"--config={config}",
                t.name,
            ]
        )


def annotate(alerts):
    """Parse an example in annoated tokens.

    markers=[
                {
                    "startRow": 0,
                    "startCol": 2,
                    "endRow": 0,
                    "endCol": 20,
                    "className": "error-marker",
                    "type": "background",
                }
            ],
    """
    tokens = []

    for _, v in json.loads(alerts).items():
        for a in v:
            tokens.append(
                {
                    "row": a["Line"] - 1,
                    "column": 0,
                    "text": a["Message"],
                    "type": "error",
                }
            )

    return tokens


def parse_rule(rule):
    """Display the source code of the user-selected rule."""
    name = STYLES / rule["extends"] / rule["ID"]
    path = str(name) + ".yml"

    yaml = ruamel.yaml.YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.preserve_quotes = True

    buf = io.StringIO()
    with open(path, "r") as f:
        data = yaml.load(f)
        desc = data["description"]
        del data["description"]
        yaml.dump(data, buf)
        return buf.getvalue(), desc


def get_rules():
    """Read our `StylesPath` into individual rules."""
    rules = []

    for rule in STYLES.glob("**/*.yml"):
        with open(rule, "r") as stream:
            data = yaml.safe_load(stream)
            desc = data.get("description", "\n\n")

            m = re.search(RE_DESC, desc, re.MULTILINE | re.DOTALL)
            rules.append(
                {
                    "ID": rule.name.split(".")[0],
                    "extends": rule.parents[0].name,
                    "description": m.group(1),
                    "category": m.group(2),
                }
            )

    return pd.DataFrame(rules)


if __name__ == "__main__":
    # st.set_page_config(layout="wide")

    # Sidebar
    st.sidebar.header("About")
    st.sidebar.markdown(
        """
        [Vale][1] is a command-line tool that brings code-like linting to
        prose. It's open source, fast, and highly customizable.

        [1]: https://github.com/errata-ai/vale
        """
    )

    st.sidebar.subheader("Links")
    st.sidebar.markdown(
        """
        - [Vale](https://github.com/errata-ai/vale)
        - [Vale Server](https://github.com/errata-ai/vale-server)
        - [Documentation](https://docs.errata.ai/)
        - [Styles](https://github.com/errata-ai/styles)
        """
    )

    st.header("Rule Explorer")
    st.markdown(
        """
        Explore community-made rules for Vale. See the [documentation][1] for
        more information on creating your own rules and styles.

        [1]: https://docs.errata.ai/vale/styles
        """
    )

    df = get_rules()

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_selection("single", use_checkbox=False)

    resp = AgGrid(
        df,
        theme="streamlit",
        gridOptions=gb.build(),
        update_mode="MODEL_CHANGED",
        fit_columns_on_grid_load=False,
    )

    st.caption("Click on a row above to learn more about a rule.")
    if len(resp["selected_rows"]):
        code, desc = parse_rule(resp["selected_rows"][0])

        st.subheader("Source")
        st.code(code, language="yaml")

        st.subheader("Example")

        m = re.search(RE_DESC, desc, re.MULTILINE | re.DOTALL)
        example = m.group(3)

        alerts = lint(example, resp["selected_rows"][0])

        st_ace(
            value=example,
            theme="kuroir",
            language="markdown",
            show_gutter=True,
            readonly=True,
            annotations=annotate(alerts),
        )
