# -*- coding: utf-8 -*-
{
    'name': 'manaTec HTML Editor Page Break',
    'summary': 'Adds page break command to HTML editor',
    'description': 'Adds page break functionality via powerbox command /pagebreak and /seitenumbruch.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Productivity',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'base',
        'html_editor',
    ],
    'data': [],
    'assets': {
        'html_editor.assets_editor': [
            'manatec_html_editor_pagebreak/static/src/page_break_plugin.js',
            'manatec_html_editor_pagebreak/static/src/page_break.scss',
        ],
        'web.report_assets_common': [
            'manatec_html_editor_pagebreak/static/src/page_break_report.scss',
        ],
        'web.report_assets_pdf': [
            'manatec_html_editor_pagebreak/static/src/page_break_report.scss',
        ],
        'web.assets_frontend': [
            'manatec_html_editor_pagebreak/static/src/page_break_report.scss',
        ],
        'html_editor.assets_readonly': [
            'manatec_html_editor_pagebreak/static/src/page_break_report.scss',
        ],
        'web.assets_web_dark': [
            'manatec_html_editor_pagebreak/static/src/**.dark.scss',
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
