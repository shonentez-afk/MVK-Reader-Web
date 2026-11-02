"""Stage111Z29C2: previously existing CSV/Copy comparators now reuse Stage111J.

No original measurement or IDP enters synthetic CI. The two input domains
remain operator-declared hypotheses and never prove same-run Delphi parity.
"""
from __future__ import annotations

import json
import pytest

from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.envelope_idr_candidate import EnvelopeProfile
from mvk_compatible.core.spectrum_summary_export_candidate import spectrum_triplet_text
from mvk_compatible.reference_compare import main as compare_csv
from mvk_compatible.triplet_reference_compare import main as compare_triplet
from .test_envelope_idr_candidate import fake_profile
from .test_offline_core import fixture_zip


@pytest.fixture
def synthetic_original_storage(tmp_path,monkeypatch):
    native=fixture_zip(tmp_path)
    idp=tmp_path/"SYNTHETIC_QA_PROFILE.idp"
    idp.write_bytes(b"test-only-not-original")
    profile=fake_profile(i=1.,q=.4)
    def loader(cls,p):
        assert str(p)==str(idp)
        return profile
    monkeypatch.setattr(
        EnvelopeProfile,"from_original_local_idp",classmethod(loader))
    session=OfflineSession.open(native)
    return native,idp,session,profile


@pytest.mark.parametrize("mode",[0,1,2,3])
def test_existing_csv_comparator_accepts_explicit_envelope_original_storage(
    synthetic_original_storage,tmp_path,capsys,mode
):
    native,idp,session,profile=synthetic_original_storage
    reference=session.spectrum_envelope(
        1,20,1024,profile,end_s=4096/65536,
        mode=mode,backend="numpy",f_range=4.,
        input_domain="original_float_storage")
    csv=tmp_path/("SYNTHETIC.original."+str(mode)+".csv")
    with csv.open("w",encoding="utf-8") as fh:
        fh.write("frequency_hz;amplitude\n")
        for hz,v in zip(reference["frequency_hz"],reference["amplitude"]):
            fh.write(f"{hz!r};{v!r}\n")
    argv=["--archive",str(native),"--idp",str(idp),
          "--reference",str(csv),"--channel","1","--code","20",
          "--n-fft","1024","--mode",str(mode),
          "--end-s","0.0625","--backend","numpy","--decimal",".",
          "--f-range","4","--input-domain","original_float_storage"]
    assert compare_csv(argv)==0
    data=json.loads(capsys.readouterr().out)
    assert data["n_bins_compared"]==512
    assert data["candidate_input_domain"]=="original_float_storage"
    assert data["within_supplied_numeric_tolerance"]
    assert data["original_app_parity_certified"] is False
    assert data["candidate_original_float_storage_verified"] is False
    assert "amplitude" not in data and "frequency_hz" not in data
    assert compare_csv(argv[:-2])==1  # default domain=calibrated BIN, not original
    wrong=json.loads(capsys.readouterr().out)
    assert wrong["candidate_input_domain"]=="calibrated_bin"
    assert wrong["within_supplied_numeric_tolerance"] is False


@pytest.mark.parametrize("mode",[0,1,2,3])
def test_existing_three_field_comparator_accepts_explicit_envelope_storage(
    synthetic_original_storage,tmp_path,capsys,mode
):
    native,idp,session,profile=synthetic_original_storage
    original=session.spectrum_envelope(
        1,20,1024,profile,end_s=4096/65536,
        mode=mode,backend="numpy",f_range=4.,
        input_domain="original_float_storage")
    copied=spectrum_triplet_text(original["spectrum_summary"],decimal_separator=",")
    ref=tmp_path/("SYNTHETIC.copy."+str(mode)+".txt")
    ref.write_text(copied,encoding="utf-8")
    argv=["--archive",str(native),"--idp",str(idp),
          "--reference",str(ref),"--channel","1",
          "--code","20","--n-fft","1024","--mode",str(mode),
          "--end-s","0.0625","--backend","numpy",
          "--f-range","4","--input-domain","original_float_storage",
          "--require-display-text"]
    assert compare_triplet(argv)==0
    row=json.loads(capsys.readouterr().out)
    assert row["candidate_input_domain"]=="original_float_storage"
    assert row["candidate_display_text_equal"] is True
    assert row["within_supplied_tolerances"]
    assert row["original_delphi_parity_verified"] is False
    assert row["candidate_original_float_storage_verified"] is False
    assert str(idp) not in json.dumps(row)
