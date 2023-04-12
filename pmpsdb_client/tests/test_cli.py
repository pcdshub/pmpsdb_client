from pmpsdb_client import __version__
from pmpsdb_client.cli import main
from pmpsdb_client.cli.parser import create_parser


def test_version(capsys):
    """
    Minimal test that we can parse input and do something
    """
    parser = create_parser()
    assert main(parser.parse_args(["--version"])) == 0
    captured = capsys.readouterr()
    assert str(__version__) in captured.out
