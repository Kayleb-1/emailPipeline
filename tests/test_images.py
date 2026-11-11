from pipeline.images import resolve_images
from pipeline.reader import read_folder
from tests.helpers import make_email

PNG = b"\x89PNG\r\n\x1a\n"


def setup(tmp_path, html, files):
    folder, _ = read_folder(make_email(tmp_path, "e1", html=html, files=files))
    return resolve_images(html, folder)


def names(images):
    return [i.path.name for i in images]


def flagged(flags):
    return sorted((f.reason, f.path) for f in flags)


def test_relative_absolute_and_cid_references_resolve(tmp_path):
    html = """
    <p><img src="inline/a.png"></p>
    <p><img src='/filestore/market_research/e1/inline/b.png'></p>
    <p><img src="cid:c.jpg@01DC1234.ABCD"></p>
    <p><img src="cid:d"></p>
    """
    files = {f"inline/{n}": PNG for n in ("a.png", "b.png", "c.jpg", "d.gif")}
    images, flags = setup(tmp_path, html, files)
    assert names(images) == ["a.png", "b.png", "c.jpg", "d.gif"]
    assert flags == []


def test_document_order_kept_not_file_order(tmp_path):
    html = '<img src="inline/z.png"><img src="inline/a.png"><img src="inline/m.png">'
    files = {f"inline/{n}": PNG for n in ("a.png", "m.png", "z.png")}
    images, _ = setup(tmp_path, html, files)
    assert names(images) == ["z.png", "a.png", "m.png"]


def test_repeated_reference_sent_once(tmp_path):
    html = '<img src="inline/logo.png"><p>x</p><img src="cid:logo.png">'
    images, flags = setup(tmp_path, html, {"inline/logo.png": PNG})
    assert names(images) == ["logo.png"] and flags == []


def test_url_encoded_and_case_mismatched_names_resolve(tmp_path):
    html = '<img src="inline/My%20Chart.PNG">'
    images, flags = setup(tmp_path, html, {"inline/my chart.png": PNG})
    assert names(images) == ["my chart.png"] and flags == []


def test_css_background_references_resolve(tmp_path):
    html = """<td background="inline/bg.png"></td>
              <div style="background-image: url('inline/hero.png')">Hero</div>"""
    images, _ = setup(tmp_path, html, {"inline/bg.png": PNG, "inline/hero.png": PNG})
    assert names(images) == ["bg.png", "hero.png"]


def test_each_image_gets_nearby_text_as_context(tmp_path):
    html = """<p>Figure 3 shows the curve steepening.</p>
              <img src="inline/chart.png" alt="UST 2s10s">
              <p>Source: Bank A estimates</p>"""
    images, _ = setup(tmp_path, html, {"inline/chart.png": PNG})
    ctx = images[0].context
    assert "alt: UST 2s10s" in ctx
    assert "before: Figure 3 shows the curve steepening." in ctx
    assert "after: Source: Bank A estimates" in ctx


def test_context_is_bounded_and_skips_scripts(tmp_path):
    html = f"""<script>var hidden = 1;</script><p>{'word ' * 400}</p>
               <img src="inline/a.png"><p>{'tail ' * 400}</p>"""
    images, _ = setup(tmp_path, html, {"inline/a.png": PNG})
    ctx = images[0].context
    assert "hidden" not in ctx
    assert len(ctx) < 500


def test_remote_and_data_images_are_ignored_not_flagged(tmp_path):
    html = """<img src="https://tracker.example.com/p.gif"><img src="//cdn.example.com/x.png">
              <img src="data:image/png;base64,AAAA">"""
    images, flags = setup(tmp_path, html, {})
    assert images == [] and flags == []


def test_missing_referenced_file_is_flagged_once(tmp_path):
    html = '<img src="inline/gone.png"><img src="inline/gone.png"><img src="cid:nope@x">'
    images, flags = setup(tmp_path, html, {})
    assert images == []
    assert flagged(flags) == [
        ("missing_image", "cid:nope@x"),
        ("missing_image", "inline/gone.png"),
    ]


def test_unreferenced_inline_files_are_flagged_not_sent(tmp_path):
    html = '<img src="inline/used.png">'
    images, flags = setup(tmp_path, html, {"inline/used.png": PNG, "inline/extra.png": PNG,
                                            "inline/sub/deep.png": PNG})
    assert names(images) == ["used.png"]
    assert flagged(flags) == [
        ("unexpected_file", "e1/inline/sub"),
        ("unreferenced_image", "e1/inline/extra.png"),
    ]


def test_no_size_filtering(tmp_path):
    html = '<img src="inline/spacer.gif" width="1" height="1">'
    images, _ = setup(tmp_path, html, {"inline/spacer.gif": b"GIF89a"})
    assert names(images) == ["spacer.gif"]


def test_no_inline_folder(tmp_path):
    html = '<img src="inline/a.png">'
    folder, _ = read_folder(make_email(tmp_path, "e2", html=html, dirs=()))
    images, flags = resolve_images(html, folder)
    assert images == []
    assert flagged(flags) == [("missing_image", "inline/a.png")]
