from pipeline.html_text import html_to_text, load_html

MARKET_TABLE = """
<table>
  <tr><th>Asset</th><th>Previous close</th><th>Current close</th><th>Change</th></tr>
  <tr><td>S&amp;P 500</td><td>6,782.81</td><td>6,950.10</td><td>+2.5%</td></tr>
  <tr><td>Bund 10y</td><td>2.61%</td><td>2.58%</td><td>-3bp</td></tr>
</table>
"""


def test_scripts_styles_comments_and_head_removed():
    html = """<html><head><title>Template</title><style>p{color:red}</style></head>
    <body><script>var x = 'secret';</script><!-- hidden comment --><p>Visible</p></body></html>"""
    assert html_to_text(html) == "Visible"


def test_text_in_reading_order_with_block_breaks():
    html = "<h1>Title</h1><p>First <b>bold</b> para.</p><div>Second</div>Line<br>break"
    assert html_to_text(html) == "Title\nFirst bold para.\nSecond\nLine\nbreak"


def test_data_table_keeps_header_and_cell_alignment():
    text = html_to_text(f"<p>Moves</p>{MARKET_TABLE}<p>After</p>")
    assert text == (
        "Moves\n\n"
        "Asset | Previous close | Current close | Change\n"
        "S&P 500 | 6,782.81 | 6,950.10 | +2.5%\n"
        "Bund 10y | 2.61% | 2.58% | -3bp\n\n"
        "After"
    )


def test_spacer_columns_dropped_and_colspan_keeps_alignment():
    html = """<table>
      <tr><td colspan="2">Market</td><td>Close</td><td>Chg</td></tr>
      <tr><td>US</td><td></td><td>6782</td><td>2.5</td></tr>
      <tr><td>EU</td><td></td><td>5400</td><td>-0.1</td></tr>
    </table>"""
    assert html_to_text(html) == "Market | Close | Chg\nUS | 6782 | 2.5\nEU | 5400 | -0.1"


def test_layout_table_with_nested_tables_is_flattened_not_piped():
    html = f"""<table><tr>
      <td><table><tr><td>Header logo text</td></tr></table></td>
      <td><p>Body paragraph one.</p><p>Body paragraph two.</p></td>
    </tr><tr><td>{MARKET_TABLE}</td><td>Footer</td></tr></table>"""
    text = html_to_text(html)
    assert "Header logo text\n" in text
    assert "Body paragraph one.\nBody paragraph two." in text
    assert "Header logo text |" not in text
    # the inner data table still keeps its structure
    assert "Asset | Previous close | Current close | Change" in text
    assert text.endswith("Footer")


def test_table_with_block_of_content_in_a_cell_is_layout():
    long = "This paragraph is long enough to be a block of content. " * 4
    html = f"<table><tr><td>A</td><td>{long}</td></tr><tr><td>B</td><td>{long}</td></tr></table>"
    text = html_to_text(html)
    assert "|" not in text
    assert text.startswith("A\n")


def test_single_column_and_single_row_tables_are_layout():
    assert html_to_text("<table><tr><td>a</td></tr><tr><td>b</td></tr></table>") == "a\nb"
    assert html_to_text("<table><tr><td>a</td><td>b</td></tr></table>") == "a\nb"


def test_lists_become_dashed_lines():
    assert html_to_text("<ul><li>One</li><li>Two</li></ul>") == "- One\n- Two"


def test_links_reduced_to_host_or_mailto_address():
    html = (
        '<p><a href="https://research.bank-a.com/r?id=1&amp;utm=xyz">Read the report</a></p>'
        '<p><a href="mailto:desk@bank-a.com?subject=hi">Contact us</a></p>'
        '<p><a href="https://bank-a.com">bank-a.com</a></p><p><a href="#top">Top</a></p>'
    )
    assert html_to_text(html) == (
        "Read the report [research.bank-a.com]\n"
        "Contact us [desk@bank-a.com]\n"
        "bank-a.com\n"
        "Top"
    )


def test_image_alt_text_kept():
    assert html_to_text('<p>Chart <img src="inline/a.png" alt="Fig 1: yields"></p>') == (
        "Chart [image: Fig 1: yields]"
    )


def test_whitespace_and_nbsp_collapsed():
    assert html_to_text("<p>  a   b \n c  </p><p></p><p></p><p>d</p>") == "a b c\nd"


def test_load_html_replaces_invalid_bytes(tmp_path):
    p = tmp_path / "emailbody.html"
    p.write_bytes(b"<meta charset='iso-8859-1'><p>Caf\xe9 \xff\xfe ok \xe2\x82\xac</p>")
    html = load_html(p)
    assert "�" in html and "€" in html
    assert html_to_text(html) == "Caf� �� ok €"


def test_malformed_html_does_not_crash():
    assert html_to_text("<table><tr><td>a<td>b</table><p>unclosed <b>bold") != ""
    assert html_to_text("") == ""
