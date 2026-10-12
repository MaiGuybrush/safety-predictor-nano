"""Issue #95: 打包探針需偵測依賴 metadata 缺失與 ONNX 載入問題。"""
import importlib.metadata as importlib_metadata
import json

import pytest

from scripts import probe_package


def _hide_metadata(monkeypatch, missing):
    real_version = importlib_metadata.version

    def fake_version(name):
        if name in missing:
            raise importlib_metadata.PackageNotFoundError(name)
        return real_version(name)

    monkeypatch.setattr(importlib_metadata, "version", fake_version)


def test_metadata_list_includes_onnx_packages():
    assert "onnx" in probe_package.DEPENDENCY_METADATA
    assert "onnxruntime" in probe_package.DEPENDENCY_METADATA


def test_third_party_imports_include_onnx_packages():
    assert "onnx" in probe_package.THIRD_PARTY_IMPORTS
    assert "onnxruntime" in probe_package.THIRD_PARTY_IMPORTS


def test_dependency_metadata_ok_when_present():
    results = probe_package._probe_dependency_metadata(["pytest"])
    assert results[0]["package"] == "pytest"
    assert results[0]["status"] == "OK"
    assert results[0]["version"]


def test_dependency_metadata_fails_when_missing(monkeypatch):
    _hide_metadata(monkeypatch, {"onnxruntime"})
    results = probe_package._probe_dependency_metadata(["onnxruntime"])
    assert results[0]["status"] == "FAIL"


def test_onnx_smoke_ok_without_autoinstall():
    result = probe_package._probe_onnx_smoke()
    assert result["status"] == "OK", result


def test_onnx_smoke_fails_instead_of_autoinstalling(monkeypatch):
    _hide_metadata(monkeypatch, {"onnxruntime"})
    calls = []
    import subprocess
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))
    result = probe_package._probe_onnx_smoke()
    assert result["status"] == "FAIL"
    assert calls == []


def test_run_probe_fails_when_metadata_missing(monkeypatch, capsys):
    _hide_metadata(monkeypatch, {"onnxruntime"})
    code = probe_package.run_probe(json_output=True)
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert report["result"] == "FAIL"
    assert "dependency_metadata" in report["sections"]
    assert "onnx_smoke" in report["sections"]
