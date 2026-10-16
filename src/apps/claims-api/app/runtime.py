from __future__ import annotations

from azure.ai.projects import AIProjectClient
from azure.identity import ManagedIdentityCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient
from openai import OpenAI

from .database import SqlClaimsStore, connection_string, connector
from .evidence import BlobEvidenceReader, EvidenceAssessment, LocalEvidenceReader, VisionClient
from .handler import ClaimHandler
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
        self.blobs: BlobServiceClient | None = None
        self.vision_client: OpenAI | None = None
        self.project: AIProjectClient | None = None
        self.agent_client: OpenAI | None = None
        self.handler: ClaimHandler | None = None
        self.evidence = EvidenceAssessment(LocalEvidenceReader())
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
        if settings.storage_account:
            self.blobs = BlobServiceClient(
                f"https://{settings.storage_account}.blob.core.windows.net",
                credential=self.credential, connection_timeout=10, read_timeout=25,
                retry_total=0,
            )
            vision = None
            if settings.vision_endpoint:
                self.vision_client = OpenAI(
                    base_url=settings.vision_endpoint,
                    api_key=get_bearer_token_provider(
                        self.credential, "https://cognitiveservices.azure.com/.default",
                    ),
                    timeout=60, max_retries=0,
                )
                vision = VisionClient(
                    self.vision_client, settings.vision_deployment, settings.vision_model_version,
                )
            self.evidence = EvidenceAssessment(BlobEvidenceReader(self.blobs), vision)
        else:
            # A cloud runtime without evidence configuration must never read local files.
            self.evidence = EvidenceAssessment(None)
        if settings.foundry_endpoint:
            self.project = AIProjectClient(
                endpoint=settings.foundry_endpoint, credential=self.credential,
                allow_preview=True,
            )
            self.agent_client = self.project.get_openai_client(
                agent_name="claim-assessor", timeout=180, max_retries=0,
            )
            self.handler = ClaimHandler(
                self.agent_client, "claim-assessor", settings.assessor_version,
            )
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
        if self.agent_client is not None:
            self.agent_client.close()
        if self.project is not None:
            self.project.close()
        if self.vision_client is not None:
            self.vision_client.close()
        if self.blobs is not None:
            self.blobs.close()
        if self.rest is not None:
            self.rest.close()
        if self.search is not None:
            self.search.close()
        if self.credential is not None:
            self.credential.close()
