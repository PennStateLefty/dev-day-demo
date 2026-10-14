from __future__ import annotations

from azure.identity import ManagedIdentityCredential
from azure.search.documents import SearchClient

from .database import SqlClaimsStore, connection_string, connector
from .knowledge import SearchPolicyKnowledge
from .search_rest import API_VERSION, SearchRestClient
from .service import DemoService
from .settings import Settings


class Runtime:
    def __init__(self, settings: Settings) -> None:
        self.store: SqlClaimsStore | None = None
        self.credential: ManagedIdentityCredential | None = None
        self.search: SearchClient | None = None
        self.rest: SearchRestClient | None = None
        if settings.mode == "local":
            self.service = DemoService()
            return
        self.store = SqlClaimsStore(
            connector(
                connection_string(
                    settings.sql_server, settings.sql_database, client_id=settings.runtime_client_id
                )
            )
        )
        self.credential = ManagedIdentityCredential(client_id=settings.runtime_client_id)
        self.search = SearchClient(
            settings.search_endpoint,
            settings.search_index,
            self.credential,
            connection_timeout=10,
            read_timeout=30,
            retry_total=2,
            api_version=API_VERSION,
        )
        self.rest = SearchRestClient(settings.search_endpoint, self.credential)
        self.service = DemoService(
            store=self.store, knowledge=SearchPolicyKnowledge(self.search, self.rest)
        )

    def probe(self) -> None:
        if self.store is not None and self.search is not None:
            self.store.probe()
            if self.search.get_document_count() == 0:
                raise RuntimeError("Search is reachable but policy knowledge has not been seeded.")

    def close(self) -> None:
        if self.rest is not None:
            self.rest.close()
        if self.search is not None:
            self.search.close()
        if self.credential is not None:
            self.credential.close()
