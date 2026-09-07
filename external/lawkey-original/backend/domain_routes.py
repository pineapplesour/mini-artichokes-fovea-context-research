from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from .domain_engine import DomainJobManager
from .domain_products import PRODUCT_PROFILES, ProductProfile, public_product_payload
from .domain_search import DomainQuery, to_selected_evidence


def install_domain_routes(
    app: FastAPI,
    *,
    domain_manager: DomainJobManager | None = None,
    domain_profiles: dict[str, ProductProfile] | None = None,
) -> DomainJobManager:
    profiles = domain_profiles or PRODUCT_PROFILES
    manager = domain_manager or DomainJobManager(profiles)

    @app.get("/api/domain-products")
    def domain_products() -> dict[str, Any]:
        return {"products": [public_product_payload(profile) for profile in profiles.values()]}

    @app.get("/api/domain/{product}/search")
    def domain_search(product: str, q: str, language: str = "", limit: int = 8) -> dict[str, Any]:
        try:
            result = manager._search.search(  # type: ignore[attr-defined]
                DomainQuery(product=product, query=q, language=language, limit=limit)
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown product") from exc
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "product": result.product,
            "query": result.query,
            "language": result.language,
            "results": [to_selected_evidence(source) for source in result.selected],
            "beta6": {
                "facets": result.facets,
                "queryStructuring": {
                    "language": result.language,
                    "surfaceFacets": result.surface_facets,
                    "expandedFacets": result.expanded_facets,
                    "familyCount": len(result.query_families),
                },
                "queryFamilies": [family.__dict__ for family in result.query_families],
                "candidateFrontier": result.candidate_frontier,
                "verifier": result.verifier,
                "rejectedLedger": [item.__dict__ for item in result.rejected_ledger],
            },
        }

    @app.post("/api/domain/{product}/answer")
    def domain_answer(product: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return manager.answer_sync(
                product=product,
                query=str(payload.get("query") or ""),
                language=str(payload.get("language") or ""),
                limit=int(payload.get("limit") or 8),
                controls=payload.get("controls") or [],
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown product") from exc
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/domain/{product}/jobs")
    def domain_create_job(product: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return manager.create_job(
                product=product,
                query=str(payload.get("query") or ""),
                language=str(payload.get("language") or ""),
                limit=int(payload.get("limit") or 8),
                controls=payload.get("controls") or [],
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown product") from exc
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/domain/jobs/{job_id}")
    def domain_get_job(job_id: str) -> dict[str, Any]:
        try:
            return manager.get_status(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.get("/api/domain/jobs/{job_id}/result")
    def domain_get_result(job_id: str) -> dict[str, Any]:
        try:
            return manager.get_result(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=425, detail=str(exc)) from exc

    @app.post("/api/domain/jobs/{job_id}/cancel")
    def domain_cancel_job(job_id: str) -> dict[str, Any]:
        try:
            return manager.cancel_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    return manager
