"""FastAPI/Jinja2: presentación de SQL F8 sin cálculos económicos en JavaScript."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

import pymysql
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import db
from src.analytics import AnalyticsQueries
from src.analytics.catalog import catalog_categories, catalog_page, latest_publication
from src.config import ConfigError, Settings, configure_logging, get_run_logger, load_settings
from src.etl.normalize import comparison_key

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")


def number(value: Decimal | int | None, places: int = 2) -> str:
    """Formato español desde Decimal; no cambia valores ni convierte a float."""

    if value is None:
        return "Sin dato"
    return format(value, f",.{places}f").translate(str.maketrans({",": ".", ".": ","}))


templates.env.filters["number"] = number


def create_app(settings: Settings | None = None, as_of: date | None = None) -> FastAPI:
    """La fecha inyectable permite contrastar HTML y SQL con fuentes congeladas."""

    app = FastAPI(title="Nortesur · Panel de negocio", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(
        request: Request,
        q: str = Query(default="", max_length=200),
        category: str = Query(default="", max_length=255),
        page: int = Query(default=1, ge=1, le=1_000_000),
    ) -> HTMLResponse:
        run_id = None
        try:
            config = settings or load_settings()
            configure_logging(config.log_level)
            with db.connect(config) as connection:
                if not db.schema_is_current(connection):
                    return templates.TemplateResponse(
                        request=request,
                        name="error.html",
                        context={
                            "message": "Falta preparar el esquema de datos. Aplica las migraciones documentadas."
                        },
                        status_code=503,
                    )
                publication = latest_publication(connection)
                run_id = publication.run_id
                analytics = AnalyticsQueries(connection, as_of, config.business_timezone)
                summary = analytics.sales_summary()
                monthly = analytics.monthly_sales()
                margin = analytics.margin_summary()
                catalog = catalog_page(connection, q, category, page)
                context = {
                    "summary": summary,
                    "monthly": monthly,
                    "margin": margin,
                    "coverage_percent": None if margin.coverage is None else margin.coverage * 100,
                    "channels": analytics.sales_by_channel(),
                    "categories": analytics.sales_by_category(),
                    "top_products": analytics.top_products(),
                    "low_stock": analytics.low_stock_products(),
                    "catalog": catalog,
                    "category_options": catalog_categories(connection),
                    "publication": publication,
                    "as_of": analytics.as_of,
                    "timezone": config.business_timezone,
                    "q": q,
                    "category": comparison_key(category) or "",
                    "previous_url": "/?"
                    + urlencode({"q": q, "category": category, "page": catalog.page - 1})
                    + "#catalogo",
                    "next_url": "/?"
                    + urlencode({"q": q, "category": category, "page": catalog.page + 1})
                    + "#catalogo",
                    "chart_data": {
                        "labels": [row.month.strftime("%m/%Y") for row in monthly],
                        "revenue": [str(row.revenue) for row in monthly],
                        "units": [row.units for row in monthly],
                    },
                }
        except (pymysql.MySQLError, ConfigError) as exc:
            # Nunca incluir el texto del error del driver (puede contener valores de conexión).
            get_run_logger("web", run_id).error("Panel no disponible (%s)", type(exc).__name__)
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={
                    "message": "No se han podido consultar los datos. Comprueba la conexión y vuelve a intentarlo."
                },
                status_code=503,
            )
        return templates.TemplateResponse(request=request, name="index.html", context=context)

    return app


app = create_app()
