from hecate.loop_factory import create_proposal


def test_proposal_file_created_with_status(tmp_path):
    p = create_proposal(
        name="cert-renewal",
        purpose="tailscale cert erneuern + nginx reload, monatlich",
        schedule="0 4 1 * *",
        command="tailscale cert && systemctl reload nginx",
        proposals_dir=tmp_path,
    )
    assert p.exists()
    text = p.read_text()
    assert "status: vorgeschlagen" in text
    assert "cert-renewal" in text
    assert "hecate.ledger" in text        # jeder neue Loop wird Ledger-instrumentiert
    assert "safety.harness" in text       # Umsetzung nur durch den Harness


def test_proposal_never_overwrites(tmp_path):
    create_proposal(name="x", purpose="p", schedule="@daily", command="true", proposals_dir=tmp_path)
    p2 = create_proposal(name="x", purpose="p", schedule="@daily", command="true", proposals_dir=tmp_path)
    assert p2.name != "x.md" or len(list(tmp_path.glob("x*.md"))) == 2
