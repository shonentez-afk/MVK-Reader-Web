"""Stage111Z31BG: untrusted local-only TLanguage resource tests."""
import hashlib
import json
import pytest
from mvk_compatible.core.original_language_resource import (
    SOURCE, SOURCE_RESOURCE_NAMES, SOURCE_DEFAULT_LANGUAGE_ID, SOURCE_RESOURCE_TYPE, inspect_local_language_bytes, inspect_local_language_file,
)


def pack(obj):
    return json.dumps(obj,ensure_ascii=False).encode("utf-8")


def test_exact_original_resource_names_and_locale_id():
    assert SOURCE_RESOURCE_NAMES==("Localization","ExtLocalization","WindowManLocalization")
    assert SOURCE_DEFAULT_LANGUAGE_ID=="ru-ru"
    assert SOURCE_RESOURCE_TYPE==10


def test_source_outer_array_locale_array_lookup_and_last_entry_wins():
    raw=pack([
        {"en":[{"Ok":"OK","Error":"Error"}],
         "ru":[{"Ok":"Да","Error":"Ошибка"},{"Ok":"ОК"}]},
        {"ru":[{"Information":"Информация"},{"Wait":"Ожидание"}]},
    ])
    found=inspect_local_language_bytes(raw,"ru")
    assert found.lookup("Ok")=="ОК"
    assert found.lookup("Error")=="Ошибка"
    assert found.lookup("Information")=="Информация"
    assert found.lookup("Wait")=="Ожидание"
    assert found.lookup("Cancel") is None
    assert found.display("Cancel")=="Отмена"
    assert found.file_sha256==hashlib.sha256(raw).hexdigest()
    assert found.report()["source"]==SOURCE
    assert found.report()["source_keys_present"]==4
    assert not found.report()["imported_local_resource_verified_as_original"]
    assert not found.report()["original_runtime_parity_verified"]
    with pytest.raises(KeyError):
        found.lookup("inventedSourceKey")


def test_locale_not_selected_does_not_fall_back_to_other_locale():
    found=inspect_local_language_bytes(
        pack([{"en":[{"Ok":"OK"}]}]),"ru")
    assert found.lookup("Ok") is None
    assert found.display("Ok")=="ОК"
    assert found.report()["source_keys_present"]==0


@pytest.mark.parametrize("value",[
    {},42,["wrong"],[{"ru":"string"}],[{"ru":[42]}],
    [{"ru":[{"Ok":3}]}],[{"ru":[{"Ok":[1]}]}],
])
def test_malformed_source_json_rejected(value):
    with pytest.raises(ValueError):
        inspect_local_language_bytes(pack(value),"ru")


def test_invalid_bytes_unsafe_name_and_no_imported_authentication(tmp_path):
    for payload in (b"",b"{}",b"[\xff]",bytes(1024*1024+1)):
        with pytest.raises((ValueError,UnicodeError)):
            inspect_local_language_bytes(payload,"ru")
    for lang in ("", "../ru","ru\n", "x"*33):
        with pytest.raises(ValueError):
            inspect_local_language_bytes(pack([{"ru":[]}]),lang)
    f=tmp_path/"ru.json"
    raw=pack([{"ru":[{"Ok":"ОК"}]}])
    f.write_bytes(raw)
    result=inspect_local_language_file(f,"ru")
    assert result.lookup("Ok")=="ОК"
    symlink=tmp_path/"link.json"
    try:
        symlink.symlink_to(f)
    except OSError:
        pytest.skip("Symlink unavailable")
    with pytest.raises(ValueError):
        inspect_local_language_file(symlink,"ru")
