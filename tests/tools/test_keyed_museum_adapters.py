"""Smithsonian, Europeana and NYPL: three sources that need a key.

Each activates on its own environment variable and reports itself unavailable
without one, so a run with no keys skips them instead of failing mid-fetch.
Nothing here touches the network: the shapes are the ones the APIs document,
and what is being tested is how each adapter reads a licence, because that is
the only thing it can get wrong that nobody notices.

The three sources state rights in three different ways, which is the point of
testing them together:

    Smithsonian   a code on the MEDIA record, and another on the object
    Europeana     a URI from a closed vocabulary
    NYPL          a sentence of prose
"""
from __future__ import annotations

import pytest

from tools.video.stock_sources import europeana, nypl, smithsonian
from tools.video.stock_sources.base import SearchFilters

FILTERS = SearchFilters(kind="image", per_page=5, page=1)


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.mark.parametrize("module,env", [
    (smithsonian, smithsonian.ENV_KEY),
    (europeana, europeana.ENV_KEY),
    (nypl, nypl.ENV_KEY),
])
class TestKeyGating:
    def _source(self, module):
        return {smithsonian: smithsonian.Smithsonian,
                europeana: europeana.Europeana,
                nypl: nypl.Nypl}[module]()

    def test_unavailable_without_its_key(self, module, env, monkeypatch):
        monkeypatch.delenv(env, raising=False)
        assert self._source(module).is_available() is False

    def test_available_with_its_key(self, module, env, monkeypatch):
        monkeypatch.setenv(env, "a-key")
        assert self._source(module).is_available() is True

    def test_searching_without_a_key_returns_nothing_and_calls_nothing(
            self, module, env, monkeypatch):
        monkeypatch.delenv(env, raising=False)

        def explode(*args, **kwargs):
            raise AssertionError("the network was called without a key")

        monkeypatch.setattr(module, "_get", explode)
        assert self._source(module).search("obelisk", FILTERS) == []

    def test_video_is_never_offered(self, module, env, monkeypatch):
        monkeypatch.setenv(env, "a-key")
        monkeypatch.setattr(module, "_get", lambda *a, **k: {})
        assert self._source(module).search(
            "obelisk", SearchFilters(kind="video", per_page=5, page=1)) == []

    def test_the_install_instructions_name_the_variable(self, module, env):
        assert env in self._source(module).install_instructions


def _smithsonian_payload(media_access, object_access="CC0"):
    return {"response": {"rows": [{
        "id": "edanmdm-1",
        "title": "A granite obelisk",
        "content": {
            "descriptiveNonRepeating": {
                "record_link": "https://www.si.edu/object/1",
                "data_source": "Freer Gallery",
                "metadata_usage": {"access": object_access},
                "online_media": {"media": [{
                    "content": "https://ids.si.edu/ids/download?id=1",
                    "thumbnail": "https://ids.si.edu/ids/thumb?id=1",
                    "usage": {"access": media_access},
                }]},
            },
            "freetext": {"topic": ["Egypt"]},
        },
    }]}}


class TestSmithsonian:
    def test_the_media_record_governs_not_the_object(self, monkeypatch):
        """The file being downloaded is the media record's, so its statement
        is the licence. The object's is carried for reading only."""
        monkeypatch.setenv(smithsonian.ENV_KEY, "k")
        monkeypatch.setattr(smithsonian, "_get",
                            lambda *a, **k: _smithsonian_payload("Usage conditions apply", "CC0"))
        assert smithsonian.Smithsonian().search("obelisk", FILTERS) == []

    def test_a_cc0_media_record_is_kept(self, monkeypatch):
        monkeypatch.setenv(smithsonian.ENV_KEY, "k")
        monkeypatch.setattr(smithsonian, "_get",
                            lambda *a, **k: _smithsonian_payload("CC0"))
        found = smithsonian.Smithsonian().search("obelisk", FILTERS)
        assert len(found) == 1
        assert found[0].extra["licence_code"] == "CC0"
        assert found[0].extra["object_access"] == "CC0"

    def test_a_record_with_no_media_is_skipped(self, monkeypatch):
        """Rather than returned with an empty download URL, which is how a
        candidate ends up in a bank with nothing behind it."""
        monkeypatch.setenv(smithsonian.ENV_KEY, "k")
        payload = _smithsonian_payload("CC0")
        payload["response"]["rows"][0]["content"][
            "descriptiveNonRepeating"]["online_media"] = {"media": []}
        monkeypatch.setattr(smithsonian, "_get", lambda *a, **k: payload)
        assert smithsonian.Smithsonian().search("obelisk", FILTERS) == []


def _europeana_payload(rights):
    return {"items": [{
        "id": "/123/abc",
        "guid": "https://www.europeana.eu/item/123/abc",
        "edmIsShownBy": ["https://provider.example/full.jpg"],
        "edmPreview": ["https://provider.example/thumb.jpg"],
        "title": ["A quarry"],
        "dcCreator": ["Anon"],
        "dataProvider": ["Rijksmuseum"],
        "country": ["Netherlands"],
        "rights": [rights],
    }]}


class TestEuropeana:
    def test_a_cc0_uri_is_kept(self, monkeypatch):
        monkeypatch.setenv(europeana.ENV_KEY, "k")
        monkeypatch.setattr(europeana, "_get", lambda *a, **k: _europeana_payload(
            "http://creativecommons.org/publicdomain/zero/1.0/"))
        found = europeana.Europeana().search("quarry", FILTERS)
        assert len(found) == 1 and found[0].extra["licence_code"] == "CC0"

    @pytest.mark.parametrize("rights", [
        "http://creativecommons.org/licenses/by-nc-sa/4.0/",
        "http://creativecommons.org/licenses/by-nd/4.0/",
        "http://rightsstatements.org/vocab/InC/1.0/",
    ])
    def test_the_uri_form_of_nc_and_nd_is_refused(self, monkeypatch, rights):
        """`.../licenses/by-nc-sa/4.0/` contains "by": a substring check for
        "CC BY" would accept every one of these, and most of Europeana is
        one of them."""
        monkeypatch.setenv(europeana.ENV_KEY, "k")
        monkeypatch.setattr(europeana, "_get",
                            lambda *a, **k: _europeana_payload(rights))
        assert europeana.Europeana().search("quarry", FILTERS) == []

    def test_everything_arrives_as_a_list_of_one(self, monkeypatch):
        monkeypatch.setenv(europeana.ENV_KEY, "k")
        monkeypatch.setattr(europeana, "_get", lambda *a, **k: _europeana_payload(
            "http://creativecommons.org/publicdomain/zero/1.0/"))
        found = europeana.Europeana().search("quarry", FILTERS)[0]
        assert found.download_url == "https://provider.example/full.jpg"
        assert found.extra["data_provider"] == "Rijksmuseum"

    def test_the_provider_is_recorded_so_a_question_has_somewhere_to_go(self, monkeypatch):
        monkeypatch.setenv(europeana.ENV_KEY, "k")
        monkeypatch.setattr(europeana, "_get", lambda *a, **k: _europeana_payload(
            "http://creativecommons.org/publicdomain/zero/1.0/"))
        found = europeana.Europeana().search("quarry", FILTERS)[0]
        assert found.extra["rights_uri"].endswith("zero/1.0/")


def _nypl_payload(rights):
    return {"nyplAPI": {"response": {"result": [{
        "uuid": "abc-123",
        "imageID": "9876",
        "title": "Obelisk at Luxor",
        "typeOfResource": "still image",
        "rightsStatement": rights,
    }]}}}


class TestNypl:
    def test_a_public_domain_sentence_is_read_as_permission(self, monkeypatch):
        monkeypatch.setenv(nypl.ENV_KEY, "t")
        monkeypatch.setattr(nypl, "_get", lambda *a, **k: _nypl_payload(
            "The New York Public Library believes that this item is in the "
            "public domain under the laws of the United States"))
        found = nypl.Nypl().search("obelisk", FILTERS)
        assert len(found) == 1 and found[0].extra["licence_code"] == "PD"

    def test_a_paragraph_about_third_party_rights_is_refused(self, monkeypatch):
        monkeypatch.setenv(nypl.ENV_KEY, "t")
        monkeypatch.setattr(nypl, "_get", lambda *a, **k: _nypl_payload(
            "The copyright and related rights status of this item has not "
            "been evaluated. Please contact the rights holder."))
        assert nypl.Nypl().search("obelisk", FILTERS) == []

    def test_a_single_result_arrives_as_a_dict_not_a_list(self, monkeypatch):
        """NYPL unwraps a one-item result, which is how an adapter that
        assumes a list quietly returns nothing."""
        monkeypatch.setenv(nypl.ENV_KEY, "t")
        payload = _nypl_payload("This item is in the public domain")
        payload["nyplAPI"]["response"]["result"] = \
            payload["nyplAPI"]["response"]["result"][0]
        monkeypatch.setattr(nypl, "_get", lambda *a, **k: payload)
        assert len(nypl.Nypl().search("obelisk", FILTERS)) == 1

    def test_an_item_with_no_image_is_skipped(self, monkeypatch):
        monkeypatch.setenv(nypl.ENV_KEY, "t")
        payload = _nypl_payload("This item is in the public domain")
        payload["nyplAPI"]["response"]["result"][0]["imageID"] = ""
        monkeypatch.setattr(nypl, "_get", lambda *a, **k: payload)
        assert nypl.Nypl().search("obelisk", FILTERS) == []
