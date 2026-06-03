"""
Tests for regional MOM6 pesize tiers in config_pes.xml.

Simulates CIME's last-match-wins logic:
  - For a given (grid, machine, pesize, compset), walk all <pes> entries in
    document order and apply each that matches; the last match wins.
  - grid/compset attributes are Python regex patterns; pesize/mach are exact
    string matches (with "any" matching everything).
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

CONFIG_PES = Path(__file__).parent.parent / "cime_config" / "config_pes.xml"


def load_all_pes_entries(path):
    """Return list of (grid_pat, mach_pat, pesize, compset_pat, values) tuples."""
    tree = ET.parse(path)
    root = tree.getroot()
    entries = []
    for grid_elem in root.findall("grid"):
        grid_pat = grid_elem.get("name", "any")
        for mach_elem in grid_elem.findall("mach"):
            mach_pat = mach_elem.get("name", "any")
            for pes_elem in mach_elem.findall("pes"):
                pesize = pes_elem.get("pesize", "any")
                compset_pat = pes_elem.get("compset", "any")
                values = {}
                for section in ("ntasks", "nthrds", "rootpe"):
                    sec_elem = pes_elem.find(section)
                    if sec_elem is not None:
                        for child in sec_elem:
                            values[child.tag] = int(child.text.strip())
                entries.append((grid_pat, mach_pat, pesize, compset_pat, values))
    return entries


def match_pes(entries, grid_alias, machine, pesize, compset):
    """
    Apply last-match-wins: return the merged dict of the last matching entry's values.
    """
    result = {}
    for grid_pat, mach_pat, pes_pesize, compset_pat, values in entries:
        # grid: "any" matches all; otherwise regex search
        if grid_pat != "any" and not re.search(grid_pat, grid_alias):
            continue
        # mach: "any" matches all; otherwise exact match
        if mach_pat != "any" and mach_pat != machine:
            continue
        # pesize: "any" matches all; otherwise exact match
        if pes_pesize != "any" and pes_pesize != pesize:
            continue
        # compset: "any" matches all; otherwise regex search
        if compset_pat != "any" and not re.search(compset_pat, compset):
            continue
        result.update(values)
    return result


# ---------------------------------------------------------------------------
# Example compsets — both MARBL-BIO orderings must be supported
# ---------------------------------------------------------------------------
REGIONAL_SICE       = "2000_DATM%NYF_SLND_SICE_MOM6%REGIONAL_SROF_SWAV_SGLC"
REGIONAL_CICE       = "2000_DATM%NYF_SLND_CICE_MOM6%REGIONAL_SROF_SWAV_SGLC"
# MARBL-BIO before REGIONAL (user-constructed)
MARBL_SICE          = "2000_DATM%NYF_SLND_SICE_MOM6%MARBL-BIO%REGIONAL_SROF_SWAV_SGLC"
MARBL_CICE          = "2000_DATM%NYF_SLND_CICE_MOM6%MARBL-BIO%REGIONAL_SROF_SWAV_SGLC"
# REGIONAL before MARBL-BIO (real CrocoDash/CESM compsets)
MARBL_SICE_REAL     = "1850_DATM%JRA_SLND_SICE_MOM6%REGIONAL%MARBL-BIO_SROF_SGLC_SWAV"
MARBL_CICE_REAL     = "1850_DATM%JRA_SLND_CICE_MOM6%REGIONAL%MARBL-BIO_SROF_SGLC_SWAV"

GRID = "any"
MACH = "derecho"


def get_pe(entries, pesize, compset):
    return match_pes(entries, GRID, MACH, pesize, compset)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
import pytest


@pytest.fixture(scope="module")
def entries():
    return load_all_pes_entries(CONFIG_PES)


# --- XS (pesize not specified → "any") ---

def test_xs_sice_ocn_tasks(entries):
    pe = get_pe(entries, "any", REGIONAL_SICE)
    assert pe["ntasks_ocn"] == 1, f"XS SICE: expected ntasks_ocn=1, got {pe['ntasks_ocn']}"

def test_xs_sice_ocn_rootpe(entries):
    pe = get_pe(entries, "any", REGIONAL_SICE)
    assert pe["rootpe_ocn"] == 0

def test_xs_sice_data_tasks(entries):
    pe = get_pe(entries, "any", REGIONAL_SICE)
    assert pe["ntasks_atm"] == 128
    assert pe["ntasks_cpl"] == 128
    assert pe["ntasks_ice"] == 128

def test_xs_marbl_sice_ocn_tasks(entries):
    # XS has no MARBL override: OCN should still be 1
    pe = get_pe(entries, "any", MARBL_SICE)
    assert pe["ntasks_ocn"] == 1, f"XS MARBL SICE: expected ntasks_ocn=1, got {pe['ntasks_ocn']}"

def test_xs_marbl_sice_rootpe(entries):
    pe = get_pe(entries, "any", MARBL_SICE)
    assert pe["rootpe_ocn"] == 0

def test_xs_cice_ocn_tasks(entries):
    pe = get_pe(entries, "any", REGIONAL_CICE)
    assert pe["ntasks_ocn"] == 1

def test_xs_marbl_cice_ocn_tasks(entries):
    pe = get_pe(entries, "any", MARBL_CICE)
    assert pe["ntasks_ocn"] == 1


# --- S ---

def test_s_sice_ocn_tasks(entries):
    pe = get_pe(entries, "S", REGIONAL_SICE)
    assert pe["ntasks_ocn"] == 128, f"S SICE: expected ntasks_ocn=128, got {pe['ntasks_ocn']}"

def test_s_sice_ocn_rootpe(entries):
    pe = get_pe(entries, "S", REGIONAL_SICE)
    assert pe["rootpe_ocn"] == 128

def test_s_sice_data_on_node0(entries):
    pe = get_pe(entries, "S", REGIONAL_SICE)
    assert pe["rootpe_atm"] == 0
    assert pe["rootpe_cpl"] == 0
    assert pe["rootpe_ice"] == 0

def test_s_marbl_sice_ocn_tasks(entries):
    pe = get_pe(entries, "S", MARBL_SICE)
    assert pe["ntasks_ocn"] == 384, f"S MARBL SICE: expected ntasks_ocn=384, got {pe['ntasks_ocn']}"

def test_s_marbl_sice_ocn_rootpe(entries):
    pe = get_pe(entries, "S", MARBL_SICE)
    assert pe["rootpe_ocn"] == 128

def test_s_cice_ocn_tasks(entries):
    pe = get_pe(entries, "S", REGIONAL_CICE)
    assert pe["ntasks_ocn"] == 128

def test_s_marbl_cice_ocn_tasks(entries):
    pe = get_pe(entries, "S", MARBL_CICE)
    assert pe["ntasks_ocn"] == 384

# Real compset ordering (REGIONAL%MARBL-BIO)
def test_s_marbl_sice_real_ocn_tasks(entries):
    pe = get_pe(entries, "S", MARBL_SICE_REAL)
    assert pe["ntasks_ocn"] == 384, f"S MARBL SICE real: expected 384, got {pe['ntasks_ocn']}"

def test_s_marbl_cice_real_ocn_tasks(entries):
    pe = get_pe(entries, "S", MARBL_CICE_REAL)
    assert pe["ntasks_ocn"] == 384


# --- M ---

def test_m_sice_ocn_tasks(entries):
    pe = get_pe(entries, "M", REGIONAL_SICE)
    assert pe["ntasks_ocn"] == 384, f"M SICE: expected ntasks_ocn=384, got {pe['ntasks_ocn']}"

def test_m_sice_ocn_rootpe(entries):
    pe = get_pe(entries, "M", REGIONAL_SICE)
    assert pe["rootpe_ocn"] == 128

def test_m_sice_data_on_node0(entries):
    pe = get_pe(entries, "M", REGIONAL_SICE)
    assert pe["rootpe_atm"] == 0
    assert pe["rootpe_cpl"] == 0
    assert pe["rootpe_ice"] == 0

def test_m_marbl_sice_ocn_tasks(entries):
    pe = get_pe(entries, "M", MARBL_SICE)
    assert pe["ntasks_ocn"] == 1152, f"M MARBL SICE: expected ntasks_ocn=1152, got {pe['ntasks_ocn']}"

def test_m_marbl_sice_ocn_rootpe(entries):
    pe = get_pe(entries, "M", MARBL_SICE)
    assert pe["rootpe_ocn"] == 128

def test_m_cice_ocn_tasks(entries):
    pe = get_pe(entries, "M", REGIONAL_CICE)
    assert pe["ntasks_ocn"] == 384

def test_m_marbl_cice_ocn_tasks(entries):
    pe = get_pe(entries, "M", MARBL_CICE)
    assert pe["ntasks_ocn"] == 1152

# Real compset ordering (REGIONAL%MARBL-BIO)
def test_m_marbl_sice_real_ocn_tasks(entries):
    pe = get_pe(entries, "M", MARBL_SICE_REAL)
    assert pe["ntasks_ocn"] == 1152, f"M MARBL SICE real: expected 1152, got {pe['ntasks_ocn']}"

def test_m_marbl_cice_real_ocn_tasks(entries):
    pe = get_pe(entries, "M", MARBL_CICE_REAL)
    assert pe["ntasks_ocn"] == 1152


# --- L ---

def test_l_sice_ocn_tasks(entries):
    pe = get_pe(entries, "L", REGIONAL_SICE)
    assert pe["ntasks_ocn"] == 896, f"L SICE: expected ntasks_ocn=896, got {pe['ntasks_ocn']}"

def test_l_sice_ocn_rootpe(entries):
    pe = get_pe(entries, "L", REGIONAL_SICE)
    assert pe["rootpe_ocn"] == 128

def test_l_sice_data_on_node0(entries):
    pe = get_pe(entries, "L", REGIONAL_SICE)
    assert pe["rootpe_atm"] == 0
    assert pe["rootpe_cpl"] == 0
    assert pe["rootpe_ice"] == 0

def test_l_marbl_sice_ocn_tasks(entries):
    pe = get_pe(entries, "L", MARBL_SICE)
    assert pe["ntasks_ocn"] == 2560, f"L MARBL SICE: expected ntasks_ocn=2560, got {pe['ntasks_ocn']}"

def test_l_marbl_sice_ocn_rootpe(entries):
    pe = get_pe(entries, "L", MARBL_SICE)
    assert pe["rootpe_ocn"] == 128

def test_l_cice_ocn_tasks(entries):
    pe = get_pe(entries, "L", REGIONAL_CICE)
    assert pe["ntasks_ocn"] == 896

def test_l_marbl_cice_ocn_tasks(entries):
    pe = get_pe(entries, "L", MARBL_CICE)
    assert pe["ntasks_ocn"] == 2560

# Real compset ordering (REGIONAL%MARBL-BIO)
def test_l_marbl_sice_real_ocn_tasks(entries):
    pe = get_pe(entries, "L", MARBL_SICE_REAL)
    assert pe["ntasks_ocn"] == 2560, f"L MARBL SICE real: expected 2560, got {pe['ntasks_ocn']}"

def test_l_marbl_cice_real_ocn_tasks(entries):
    pe = get_pe(entries, "L", MARBL_CICE_REAL)
    assert pe["ntasks_ocn"] == 2560


# --- Non-regional compset should NOT match regional entries on derecho ---

def test_non_regional_not_matched_by_xs(entries):
    non_regional = "2000_DATM%NYF_SLND_CICE_MOM6%SIS2_SROF_SWAV_SGLC"
    pe = get_pe(entries, "any", non_regional)
    # Should fall through to the global default (-1 = 1 node), not our 128-task entry
    assert pe.get("ntasks_ocn") == -1, (
        f"Non-regional compset should not match regional entry; got ntasks_ocn={pe.get('ntasks_ocn')}"
    )
