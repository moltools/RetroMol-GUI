"""Helpers to interact with NCBI APIs."""

import time
import requests
from typing import Any


def nuccore_to_gcf(
    nuccore_acc: str,
    *,
    api_key: str | None = None,
    email: str | None = None,
    tool: str = "bionexus",
    timeout: float = 15.0,
    retries: int = 3,
    sleep_between: float = 0.34,  # ~3 requests/sec (NCBI-safe)
    
) -> str | None:
    """
    Resolve a nuccore accession to a RefSeq assembly accession (GCF_*).

    :param nuccore_acc: nuccore accession
    :param api_key: NCBI API key (optional)
    :param email: contact email (optional)
    :param tool: tool name for NCBI eutils (default: "bionexus")
    :param timeout: request timeout in seconds (default: 15.0)
    :param retries: number of retries for requests (default: 3)
    :param sleep_between: sleep time between requests in seconds (default: 0.34)
    :return: GCF_XXXXXXXX.X assembly accession, or None if not found
    """
    session = requests.Session()

    base_params = {"retmode": "json", "tool": tool}
    if api_key:
        base_params["api_key"] = api_key
    if email:
        base_params["email"] = email

    def _get(url: str, params: dict) -> dict[str, Any]:
        """
        Helper to perform GET request with retries.
        
        :param url: request URL
        :param params: request parameters
        :return: JSON response as dictionary
        """
        last_err = None
        for _ in range(retries):
            try:
                r = session.get(url, params=params, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                time.sleep(sleep_between)
        raise last_err

    # elink: nuccore -> assembly UID
    elink_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
    elink_params = {
        **base_params,
        "dbfrom": "nuccore",
        "db": "assembly",
        "id": nuccore_acc,
    }

    data = _get(elink_url, elink_params)

    linksets = data.get("linksets") or []
    linksetdbs = (linksets[0].get("linksetdbs") if linksets else []) or []

    assembly_uid = None
    for db in linksetdbs:
        if db.get("dbto") == "assembly" and db.get("links"):
            assembly_uid = db["links"][0]
            break

    if not assembly_uid:
        return None

    time.sleep(sleep_between)

    # esummary: assembly UID -> GCF accession
    esum_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    esum_params = {
        **base_params,
        "db": "assembly",
        "id": assembly_uid,
    }

    summary = _get(esum_url, esum_params)
    doc = summary.get("result", {}).get(str(assembly_uid))

    if not doc:
        return None

    return doc.get("assemblyaccession")
