from pipeline.reader import discover_emails, email_dirs, read_folder
from tests.helpers import make_email


def reasons(flags):
    return sorted((f.path, f.reason) for f in flags)


def test_plain_email_has_no_flags(tmp_path):
    folder, flags = read_folder(make_email(tmp_path, "001"))
    assert flags == []
    assert folder.source_file == "001"
    assert folder.html_path == tmp_path / "001" / "emailbody.html"
    assert folder.pdf_paths == []
    assert folder.inline_dir == tmp_path / "001" / "inline"


def test_missing_html_is_flagged_and_marked_for_skip(tmp_path):
    folder, flags = read_folder(make_email(tmp_path, "002", html=None))
    assert folder.html_path is None
    assert reasons(flags) == [("002/emailbody.html", "missing_html")]


def test_html_name_matched_case_insensitively(tmp_path):
    p = make_email(tmp_path, "003", html=None, files={"EmailBody.HTML": "<p>x</p>"})
    folder, flags = read_folder(p)
    assert folder.html_path == p / "EmailBody.HTML"
    assert flags == []


def test_pdfs_found_in_any_case_and_sorted(tmp_path):
    p = make_email(tmp_path, "004", files={"b.PDF": b"%PDF", "a.pdf": b"%PDF", "C.Pdf": b"%PDF"})
    folder, flags = read_folder(p)
    assert [x.name for x in folder.pdf_paths] == ["a.pdf", "b.PDF", "C.Pdf"]
    assert flags == []


def test_missing_inline_and_thumbs_are_normal(tmp_path):
    folder, flags = read_folder(make_email(tmp_path, "005", dirs=()))
    assert folder.inline_dir is None
    assert flags == []


def test_inline_contents_left_to_image_resolution(tmp_path):
    p = make_email(tmp_path, "006", files={"inline/logo.png": b"png"})
    _, flags = read_folder(p)
    assert flags == []


def test_anything_in_thumbs_is_flagged(tmp_path):
    p = make_email(tmp_path, "007", files={"thumbs/t1.png": b"x", "thumbs/sub/t2.png": b"x"})
    _, flags = read_folder(p)
    assert reasons(flags) == [
        ("007/thumbs/sub/t2.png", "unexpected_file"),
        ("007/thumbs/t1.png", "unexpected_file"),
    ]


def test_extra_files_and_folders_are_flagged(tmp_path):
    p = make_email(
        tmp_path, "008",
        files={"model.xlsx": b"x", "chart.jpg": b"x", "extra/notes.txt": "x"},
    )
    folder, flags = read_folder(p)
    assert reasons(flags) == [
        ("008/chart.jpg", "unexpected_file"),
        ("008/extra", "unexpected_file"),
        ("008/model.xlsx", "unexpected_file"),
    ]
    assert folder.pdf_paths == []


def test_folder_named_like_pdf_is_not_a_pdf(tmp_path):
    p = make_email(tmp_path, "009", files={"weird.pdf/inner.txt": "x"})
    folder, flags = read_folder(p)
    assert folder.pdf_paths == []
    assert reasons(flags) == [("009/weird.pdf", "unexpected_file")]


def test_discover_emails_sorted_and_includes_folders_without_html(tmp_path):
    make_email(tmp_path, "b")
    make_email(tmp_path, "a", html=None)
    (tmp_path / "stray.txt").write_text("not a folder")
    folders = discover_emails(tmp_path)
    assert [f.source_file for f in folders] == ["a", "b"]
    assert folders[0].html_path is None
    assert [d.name for d in email_dirs(tmp_path)] == ["a", "b"]
