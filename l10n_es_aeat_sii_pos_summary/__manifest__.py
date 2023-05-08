{
    "name": "Resumen de TPV al SII",
    "category": "Accounting & Finance",
    "summary": "Permite enviar un resumen de la sesión del tpv al sii",
    "version": "14.0.1.0.0",
    "author": "Aures Tic, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-spain",
    "license": "AGPL-3",
    "development_status": "Alpha",
    "depends": [
        "point_of_sale",
        "l10n_es_pos",
        "l10n_es_aeat",
        "l10n_es_aeat_sii_oca",
    ],
    "data": ["views/pos_session_view.xml", "views/res_company_view.xml"],
    "demo": [],
    "installable": True,
}
