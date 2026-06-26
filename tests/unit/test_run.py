import sys
from io import StringIO
from unittest.mock import patch

import pytest

from web_agent import run


def test_stdin_executes_code():
    stdout = StringIO()
    fake_stdin = StringIO("print('hello from stdin')")

    with patch.object(sys, "argv", ["web-agent"]), \
         patch("web_agent.run.ensure_daemon"), \
         patch("web_agent.run.print_update_banner"), \
         patch("sys.stdin", fake_stdin), \
         patch("sys.stdout", stdout):
        run.main()

    assert stdout.getvalue().strip() == "hello from stdin"


def test_c_flag_is_rejected():
    with patch.object(sys, "argv", ["web-agent", "-c", "print('old path')"]), \
         patch("sys.stdin", StringIO("print('ignored')")):
        try:
            run.main()
        except SystemExit as e:
            assert "web-agent <<'PY'" in str(e)
        else:
            raise AssertionError("-c should be rejected")


def test_no_args_interactive_stdin_prints_usage():
    fake_stdin = StringIO("")
    fake_stdin.isatty = lambda: True

    with patch.object(sys, "argv", ["web-agent"]), \
         patch("sys.stdin", fake_stdin):
        try:
            run.main()
        except SystemExit as e:
            assert "web-agent <<'PY'" in str(e)
        else:
            raise AssertionError("interactive no-args invocation should exit with usage")


def test_no_args_empty_stdin_prints_usage():
    with patch.object(sys, "argv", ["web-agent"]), \
         patch("sys.stdin", StringIO("")):
        try:
            run.main()
        except SystemExit as e:
            assert "web-agent <<'PY'" in str(e)
        else:
            raise AssertionError("empty stdin should exit with usage")




def test_local_chrome_listening_rejects_non_chrome():
    """9222/9223 上的裸 TCP 监听器不能欺骗探测 —— 只有真实的
    /json/version 响应才算作 Chrome。"""
    with patch("web_agent.run.urllib.request.urlopen", side_effect=OSError):
        assert run._local_chrome_listening() is False
    with patch("web_agent.run.urllib.request.urlopen") as mock_open:
        assert run._local_chrome_listening() is True
        mock_open.assert_called_once()


def test_cli_doctor_fix_snap_invokes_guide():
    with patch.object(sys, "argv", ["web-agent", "doctor", "--fix-snap"]), \
         patch("web_agent.run.run_doctor_fix_snap", return_value=0) as m:
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 0
    m.assert_called_once()


def test_cli_doctor_rejects_unknown_flags():
    err = StringIO()
    with patch.object(sys, "argv", ["web-agent", "doctor", "--bogus"]), patch("sys.stderr", err):
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 2
    assert "usage" in err.getvalue().lower()
