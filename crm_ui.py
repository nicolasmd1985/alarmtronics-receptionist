"""
crm_ui.py - Modern, responsive, accessible CRM dashboard for Alarmtronics Leads.
Served at GET /leads (HTML) and backed by /api/leads REST endpoints.
"""

from html import escape


def render_leads_crm_html(
    company_name: str = "Alarmtronics",
    telnyx_number: str = "+14073050475",
    forward_number: str = "+19043850725",
) -> str:
    safe_company = escape(company_name)
    safe_telnyx = escape(telnyx_number)
    safe_forward = escape(forward_number)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <title>CRM de Llamadas y Tickets — {safe_company}</title>
  <style>
    :root {{
      /* Light mode palette (default fallback for older browsers) */
      --bg-page-light: #f1f5f9;
      --bg-surface-light: #ffffff;
      --bg-subtle-light: #f8fafc;
      --bg-hover-light: #eef6ff;
      --border-light: #cbd5e1;
      --border-subtle-light: #e2e8f0;
      --text-primary-light: #0f172a;
      --text-secondary-light: #475569;
      --text-muted-light: #64748b;
      --brand-light: #0284c7;
      --brand-hover-light: #0369a1;
      --brand-soft-light: #e0f2fe;
      --brand-text-light: #ffffff;
      --scrollbar-track-light: #e2e8f0;
      --scrollbar-thumb-light: #64748b;
      --shadow-light: 0 4px 16px rgba(15, 23, 42, 0.08);

      /* Dark mode palette */
      --bg-page-dark: #090e1a;
      --bg-surface-dark: #111827;
      --bg-subtle-dark: #1e293b;
      --bg-hover-dark: #172554;
      --border-dark: #334155;
      --border-subtle-dark: #1f2937;
      --text-primary-dark: #f8fafc;
      --text-secondary-dark: #cbd5e1;
      --text-muted-dark: #94a3b8;
      --brand-dark: #38bdf8;
      --brand-hover-dark: #7dd3fc;
      --brand-soft-dark: rgba(56, 189, 248, 0.14);
      --brand-text-dark: #082f49;
      --scrollbar-track-dark: #0f172a;
      --scrollbar-thumb-dark: #475569;
      --shadow-dark: 0 12px 32px rgba(0, 0, 0, 0.55);

      /* Resolved tokens (light default) */
      --bg-page: var(--bg-page-light);
      --bg-surface: var(--bg-surface-light);
      --bg-subtle: var(--bg-subtle-light);
      --bg-hover: var(--bg-hover-light);
      --border: var(--border-light);
      --border-subtle: var(--border-subtle-light);
      --text-primary: var(--text-primary-light);
      --text-secondary: var(--text-secondary-light);
      --text-muted: var(--text-muted-light);
      --brand: var(--brand-light);
      --brand-hover: var(--brand-hover-light);
      --brand-soft: var(--brand-soft-light);
      --brand-text: var(--brand-text-light);
      --scrollbar-track: var(--scrollbar-track-light);
      --scrollbar-thumb: var(--scrollbar-thumb-light);
      --shadow: var(--shadow-light);

      /* Fallback for browsers without light-dark() */
      @media (prefers-color-scheme: dark) {{
        --bg-page: var(--bg-page-dark);
        --bg-surface: var(--bg-surface-dark);
        --bg-subtle: var(--bg-subtle-dark);
        --bg-hover: var(--bg-hover-dark);
        --border: var(--border-dark);
        --border-subtle: var(--border-subtle-dark);
        --text-primary: var(--text-primary-dark);
        --text-secondary: var(--text-secondary-dark);
        --text-muted: var(--text-muted-dark);
        --brand: var(--brand-dark);
        --brand-hover: var(--brand-hover-dark);
        --brand-soft: var(--brand-soft-dark);
        --brand-text: var(--brand-text-dark);
        --scrollbar-track: var(--scrollbar-track-dark);
        --scrollbar-thumb: var(--scrollbar-thumb-dark);
        --shadow: var(--shadow-dark);
      }}

      /* Modern light-dark() resolution synced with color-scheme */
      @supports (color: light-dark(white, black)) {{
        --bg-page: light-dark(var(--bg-page-light), var(--bg-page-dark));
        --bg-surface: light-dark(var(--bg-surface-light), var(--bg-surface-dark));
        --bg-subtle: light-dark(var(--bg-subtle-light), var(--bg-subtle-dark));
        --bg-hover: light-dark(var(--bg-hover-light), var(--bg-hover-dark));
        --border: light-dark(var(--border-light), var(--border-dark));
        --border-subtle: light-dark(var(--border-subtle-light), var(--border-subtle-dark));
        --text-primary: light-dark(var(--text-primary-light), var(--text-primary-dark));
        --text-secondary: light-dark(var(--text-secondary-light), var(--text-secondary-dark));
        --text-muted: light-dark(var(--text-muted-light), var(--text-muted-dark));
        --brand: light-dark(var(--brand-light), var(--brand-dark));
        --brand-hover: light-dark(var(--brand-hover-light), var(--brand-hover-dark));
        --brand-soft: light-dark(var(--brand-soft-light), var(--brand-soft-dark));
        --brand-text: light-dark(var(--brand-text-light), var(--brand-text-dark));
        --scrollbar-track: light-dark(var(--scrollbar-track-light), var(--scrollbar-track-dark));
        --scrollbar-thumb: light-dark(var(--scrollbar-thumb-light), var(--scrollbar-thumb-dark));
      }}

      color-scheme: light dark;
      accent-color: var(--brand);
      scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
    }}

    :root[data-theme="dark"] {{
      color-scheme: dark;
      --bg-page: var(--bg-page-dark);
      --bg-surface: var(--bg-surface-dark);
      --bg-subtle: var(--bg-subtle-dark);
      --bg-hover: var(--bg-hover-dark);
      --border: var(--border-dark);
      --border-subtle: var(--border-subtle-dark);
      --text-primary: var(--text-primary-dark);
      --text-secondary: var(--text-secondary-dark);
      --text-muted: var(--text-muted-dark);
      --brand: var(--brand-dark);
      --brand-hover: var(--brand-hover-dark);
      --brand-soft: var(--brand-soft-dark);
      --brand-text: var(--brand-text-dark);
      --scrollbar-track: var(--scrollbar-track-dark);
      --scrollbar-thumb: var(--scrollbar-thumb-dark);
      --shadow: var(--shadow-dark);
    }}

    :root[data-theme="light"] {{
      color-scheme: light;
      --bg-page: var(--bg-page-light);
      --bg-surface: var(--bg-surface-light);
      --bg-subtle: var(--bg-subtle-light);
      --bg-hover: var(--bg-hover-light);
      --border: var(--border-light);
      --border-subtle: var(--border-subtle-light);
      --text-primary: var(--text-primary-light);
      --text-secondary: var(--text-secondary-light);
      --text-muted: var(--text-muted-light);
      --brand: var(--brand-light);
      --brand-hover: var(--brand-hover-light);
      --brand-soft: var(--brand-soft-light);
      --brand-text: var(--brand-text-light);
      --scrollbar-track: var(--scrollbar-track-light);
      --scrollbar-thumb: var(--scrollbar-thumb-light);
      --shadow: var(--shadow-light);
    }}

    @supports not (scrollbar-color: auto) {{
      .table-wrapper {{
        scrollbar-width: auto;
      }}
      .table-wrapper::-webkit-scrollbar {{
        width: 10px;
        height: 10px;
      }}
      .table-wrapper::-webkit-scrollbar-thumb {{
        background: var(--scrollbar-thumb);
        border-radius: 6px;
      }}
      .table-wrapper::-webkit-scrollbar-track {{
        background: var(--scrollbar-track);
      }}
    }}

    *, *::before, *::after {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
      background: var(--bg-page);
      color: var(--text-primary);
      line-height: 1.5;
      min-block-size: 100dvh;
    }}

    .sr-only {{
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip-path: inset(50%);
      white-space: nowrap;
      border: 0;
    }}

    /* Top Navigation Bar */
    .topbar {{
      background: var(--bg-surface);
      border-bottom: 1px solid var(--border);
      padding: 0.9rem 1.5rem;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      position: sticky;
      inset-block-start: 0;
      z-index: 20;
    }}

    .brand-group {{
      display: flex;
      align-items: center;
      gap: 0.85rem;
    }}

    .brand-icon {{
      inline-size: 40px;
      block-size: 40px;
      border-radius: 10px;
      background: var(--brand-soft);
      color: var(--brand);
      display: grid;
      place-items: center;
      font-size: 1.25rem;
      font-weight: 800;
      border: 1px solid var(--brand);
    }}

    .brand-title {{
      margin: 0;
      font-size: 1.15rem;
      font-weight: 800;
      letter-spacing: -0.01em;
    }}

    .brand-sub {{
      font-size: 0.8rem;
      color: var(--text-muted);
    }}

    .topbar-actions {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.55rem;
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      padding: 0.5rem 0.9rem;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--bg-subtle);
      color: var(--text-primary);
      font-size: 0.86rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      min-block-size: 36px;
      transition: background 0.15s ease, border-color 0.15s ease;
    }}

    .btn:hover {{
      background: var(--bg-hover);
      border-color: var(--brand);
    }}

    .btn:focus-visible {{
      outline: 2px solid var(--brand);
      outline-offset: 2px;
    }}

    .btn-primary {{
      background: var(--brand);
      color: var(--brand-text);
      border-color: var(--brand);
    }}

    .btn-primary:hover {{
      background: var(--brand-hover);
      border-color: var(--brand-hover);
      color: var(--brand-text);
    }}

    .btn-danger {{
      background: #dc2626;
      color: #ffffff;
      border-color: #dc2626;
    }}

    .btn-danger:hover {{
      background: #b91c1c;
      border-color: #b91c1c;
    }}

    .btn-icon {{
      padding: 0.35rem 0.55rem;
      min-block-size: 30px;
      font-size: 0.8rem;
    }}

    /* Main Container */
    .container {{
      max-inline-size: 1440px;
      margin-inline: auto;
      padding: 1.25rem 1.5rem 2.5rem;
    }}

    /* KPI Strip */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 0.9rem;
      margin-block-end: 1.25rem;
    }}

    .kpi-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.15rem;
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      cursor: pointer;
      text-align: left;
      color: inherit;
      transition: border-color 0.15s ease, transform 0.15s ease;
    }}

    .kpi-card:hover {{
      border-color: var(--brand);
      transform: translateY(-1px);
    }}

    .kpi-card[aria-pressed="true"] {{
      border-color: var(--brand);
      box-shadow: 0 0 0 2px var(--brand-soft);
    }}

    .kpi-label {{
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--text-muted);
    }}

    .kpi-value {{
      font-size: 1.75rem;
      font-weight: 800;
      line-height: 1.15;
    }}

    .kpi-hint {{
      font-size: 0.78rem;
      color: var(--text-secondary);
    }}

    /* Filters Panel */
    .filters-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.15rem;
      margin-block-end: 1.15rem;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
    }}

    .filters-row {{
      display: grid;
      grid-template-columns: minmax(240px, 2fr) repeat(auto-fit, minmax(155px, 1fr));
      gap: 0.7rem;
      align-items: end;
    }}

    .field {{
      display: flex;
      flex-direction: column;
      gap: 0.3rem;
    }}

    .field label {{
      font-size: 0.76rem;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}

    .field input,
    .field select,
    .detail-select,
    .detail-textarea {{
      background: var(--bg-subtle);
      color: var(--text-primary);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.5rem 0.7rem;
      font-size: 0.88rem;
      font-family: inherit;
      min-block-size: 38px;
    }}

    .field input:focus-visible,
    .field select:focus-visible,
    .detail-select:focus-visible,
    .detail-textarea:focus-visible {{
      outline: 2px solid var(--brand);
      outline-offset: 1px;
    }}

    .filters-footer {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      padding-top: 0.55rem;
      border-top: 1px solid var(--border-subtle);
    }}

    .custom-dates {{
      display: none;
      gap: 0.6rem;
      flex-wrap: wrap;
      align-items: end;
    }}

    .custom-dates.visible {{
      display: flex;
    }}

    .checkbox-label {{
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      font-size: 0.86rem;
      font-weight: 600;
      color: var(--text-secondary);
      cursor: pointer;
    }}

    .results-meta {{
      font-size: 0.85rem;
      color: var(--text-muted);
      font-weight: 600;
    }}

    /* Table Wrapper & Responsive Table */
    .table-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .table-wrapper {{
      overflow: auto;
      max-inline-size: 100%;
      max-block-size: min(68vh, 720px);
      container-type: inline-size;
    }}

    .table-wrapper:focus-visible {{
      outline: 2px solid var(--brand);
      outline-offset: -2px;
    }}

    table {{
      inline-size: 100%;
      min-inline-size: 980px;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 0.88rem;
      --label-2: "Fecha";
      --label-3: "Teléfono";
      --label-4: "Dirección";
      --label-5: "Problema / Sistema";
      --label-6: "Urgencia";
      --label-7: "Estado CRM";
      --label-8: "Duración";
      --label-9: "Acciones";
    }}

    caption {{
      text-align: left;
      padding: 0.85rem 1.15rem;
      font-weight: 700;
      font-size: 0.92rem;
      color: var(--text-secondary);
      background: var(--bg-subtle);
      border-bottom: 1px solid var(--border);
    }}

    thead {{
      position: sticky;
      inset-block-start: 0;
      z-index: 3;
      background: var(--bg-subtle);
    }}

    thead th {{
      text-align: left;
      font-size: 0.77rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--text-muted);
      padding: 0.75rem 0.85rem;
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
      background: var(--bg-subtle);
    }}

    /* Drop padding only on th containing a sort button so button fills cell */
    thead th:has(> button) {{
      padding: 0;
    }}

    thead th > button {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.45rem;
      inline-size: 100%;
      min-block-size: 40px;
      padding: 0.75rem 0.85rem;
      border: 0;
      background: transparent;
      color: inherit;
      font: inherit;
      letter-spacing: inherit;
      text-transform: inherit;
      cursor: pointer;
      text-align: left;
    }}

    thead th > button:hover {{
      color: var(--text-primary);
      background: var(--bg-hover);
    }}

    thead th > button:focus-visible {{
      outline: 2px solid var(--brand);
      outline-offset: -2px;
    }}

    .sort-icon {{
      display: inline-block;
      inline-size: 1em;
      text-align: center;
      opacity: 0.35;
      color: currentColor;
      flex-shrink: 0;
    }}

    th[aria-sort] > button {{
      color: var(--brand);
    }}

    th[aria-sort] .sort-icon {{
      opacity: 1;
    }}

    th[aria-sort="ascending"] .sort-icon::before {{
      content: "▲";
    }}

    th[aria-sort="descending"] .sort-icon::before {{
      content: "▼";
    }}

    th:not([aria-sort]) .sort-icon::before {{
      content: "⇅";
    }}

    tbody tr {{
      view-transition-name: match-element;
      transition: background 0.12s ease;
    }}

    tbody tr:hover td,
    tbody tr:hover th {{
      background: var(--bg-hover);
    }}

    tbody tr[hidden] {{
      display: none;
    }}

    tbody th {{
      position: sticky;
      inset-inline-start: 0;
      z-index: 2;
      background: var(--bg-surface);
      text-align: left;
      font-weight: 700;
      padding: 0.75rem 0.85rem;
      border-bottom: 1px solid var(--border-subtle);
      min-inline-size: 185px;
      max-inline-size: 240px;
    }}

    tbody td {{
      padding: 0.75rem 0.85rem;
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: middle;
      background: var(--bg-surface);
    }}

    @media (prefers-reduced-motion: reduce) {{
      ::view-transition-group(*),
      ::view-transition-old(*),
      ::view-transition-new(*) {{
        animation: none;
      }}
    }}

    /* Cell Helpers */
    .client-cell {{
      display: flex;
      align-items: center;
      gap: 0.65rem;
    }}

    .avatar {{
      inline-size: 32px;
      block-size: 32px;
      border-radius: 999px;
      background: var(--brand-soft);
      color: var(--brand);
      font-size: 0.78rem;
      font-weight: 800;
      display: grid;
      place-items: center;
      flex-shrink: 0;
    }}

    .client-name {{
      font-weight: 700;
      color: var(--text-primary);
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-inline-size: 170px;
    }}

    .client-sub {{
      font-size: 0.74rem;
      color: var(--text-muted);
      font-weight: 500;
      display: block;
    }}

    .phone-link {{
      color: var(--brand);
      text-decoration: none;
      font-weight: 600;
      white-space: nowrap;
    }}

    .phone-link:hover {{
      text-decoration: underline;
    }}

    .addr-text {{
      display: block;
      max-inline-size: 230px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .issue-text {{
      display: block;
      max-inline-size: 250px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--text-primary);
    }}

    .sys-tag {{
      display: inline-block;
      margin-top: 0.2rem;
      font-size: 0.72rem;
      padding: 0.1rem 0.45rem;
      border-radius: 5px;
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-weight: 600;
    }}

    /* Badges */
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      padding: 0.22rem 0.6rem;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 700;
      white-space: nowrap;
    }}

    .pill-emergency {{
      background: rgba(239, 68, 68, 0.16);
      color: #ef4444;
      border: 1px solid rgba(239, 68, 68, 0.45);
    }}

    .pill-urgent {{
      background: rgba(245, 158, 11, 0.16);
      color: #d97706;
      border: 1px solid rgba(245, 158, 11, 0.45);
    }}

    .pill-normal {{
      background: rgba(56, 189, 248, 0.14);
      color: var(--brand);
      border: 1px solid rgba(56, 189, 248, 0.35);
    }}

    .status-select {{
      background: var(--bg-subtle);
      color: var(--text-primary);
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 0.3rem 0.5rem;
      font-size: 0.8rem;
      font-weight: 700;
      cursor: pointer;
    }}

    .status-select[data-status="nuevo"] {{
      border-color: #38bdf8;
    }}
    .status-select[data-status="en_progreso"] {{
      border-color: #f59e0b;
    }}
    .status-select[data-status="agendado"] {{
      border-color: #a855f7;
    }}
    .status-select[data-status="resuelto"] {{
      border-color: #10b981;
    }}
    .status-select[data-status="descartado"] {{
      opacity: 0.65;
    }}

    .actions-cell {{
      display: flex;
      align-items: center;
      gap: 0.35rem;
      white-space: nowrap;
    }}

    .empty-state {{
      padding: 3rem 1.5rem;
      text-align: center;
      color: var(--text-muted);
    }}

    /* Container Query Responsive Stacked Cards (< 760px) */
    @container (width < 760px) {{
      table {{
        min-inline-size: 0;
      }}
      table, thead, tbody, tr, th, td {{
        display: block;
      }}
      thead {{
        display: none;
      }}
      tbody {{
        padding: 0.75rem;
      }}
      tbody tr {{
        margin-block-end: 1rem;
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
      }}
      tbody th {{
        position: sticky;
        inset-block-start: 0;
        z-index: 2;
        background: var(--bg-subtle);
        max-inline-size: none;
        border-bottom: 1px solid var(--border);
      }}
      tbody td {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.75rem;
        text-align: right;
      }}
      tbody td::before {{
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        color: var(--text-muted);
        text-align: left;
        flex-shrink: 0;
      }}
      tbody td:nth-child(2)::before {{ content: var(--label-2) ": "; }}
      tbody td:nth-child(3)::before {{ content: var(--label-3) ": "; }}
      tbody td:nth-child(4)::before {{ content: var(--label-4) ": "; }}
      tbody td:nth-child(5)::before {{ content: var(--label-5) ": "; }}
      tbody td:nth-child(6)::before {{ content: var(--label-6) ": "; }}
      tbody td:nth-child(7)::before {{ content: var(--label-7) ": "; }}
      tbody td:nth-child(8)::before {{ content: var(--label-8) ": "; }}
      tbody td:nth-child(9)::before {{ content: var(--label-9) ": "; }}
      .addr-text, .issue-text, .client-name {{
        max-inline-size: 100%;
        white-space: normal;
      }}
    }}

    /* Native Modal Dialogs */
    dialog {{
      border: 1px solid var(--border);
      border-radius: 14px;
      background: var(--bg-surface);
      color: var(--text-primary);
      padding: 0;
      max-inline-size: min(760px, calc(100vw - 2rem));
      inline-size: 100%;
      max-block-size: calc(100dvh - 2.5rem);
      box-shadow: var(--shadow);
      margin: auto;
    }}

    dialog[open] {{
      display: flex;
      flex-direction: column;
    }}

    dialog:modal {{
      overscroll-behavior: contain;
    }}

    dialog::backdrop {{
      background: rgba(2, 6, 23, 0.72);
      backdrop-filter: blur(3px);
      overflow: hidden;
      overscroll-behavior: contain;
    }}

    .dialog-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 1.1rem 1.35rem;
      border-bottom: 1px solid var(--border);
      background: var(--bg-subtle);
    }}

    .dialog-header h1 {{
      margin: 0;
      font-size: 1.15rem;
      font-weight: 800;
    }}

    .dialog-body {{
      padding: 1.25rem 1.35rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1.1rem;
    }}

    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 0.75rem;
    }}

    .detail-box {{
      background: var(--bg-subtle);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 0.75rem 0.9rem;
    }}

    .detail-box-label {{
      font-size: 0.73rem;
      text-transform: uppercase;
      font-weight: 700;
      color: var(--text-muted);
      margin-bottom: 0.25rem;
    }}

    .detail-box-val {{
      font-size: 0.94rem;
      font-weight: 600;
      word-break: break-word;
    }}

    .summary-box {{
      background: var(--brand-soft);
      border: 1px solid var(--brand);
      border-radius: 10px;
      padding: 0.9rem 1rem;
      font-size: 0.92rem;
    }}

    .crm-edit-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 0.75rem;
    }}

    .detail-textarea {{
      inline-size: 100%;
      min-block-size: 80px;
      resize: vertical;
    }}

    .transcript-list {{
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
      max-block-size: 280px;
      overflow-y: auto;
      padding: 0.75rem;
      background: var(--bg-page);
      border: 1px solid var(--border);
      border-radius: 10px;
    }}

    .bubble {{
      padding: 0.6rem 0.85rem;
      border-radius: 10px;
      max-inline-size: 88%;
      font-size: 0.88rem;
      line-height: 1.45;
    }}

    .bubble-assistant {{
      align-self: flex-start;
      background: var(--bg-surface);
      border: 1px solid var(--border);
    }}

    .bubble-caller {{
      align-self: flex-end;
      background: var(--brand-soft);
      border: 1px solid var(--brand);
    }}

    .bubble-role {{
      display: block;
      font-size: 0.7rem;
      font-weight: 800;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 0.2rem;
    }}

    .dialog-footer {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 0.6rem;
      padding: 0.95rem 1.35rem;
      border-top: 1px solid var(--border);
      background: var(--bg-subtle);
    }}

    #delete-confirm-dialog {{
      max-inline-size: 440px;
    }}

    .toast {{
      position: fixed;
      inset-block-end: 1.25rem;
      inset-inline-end: 1.25rem;
      background: #0f172a;
      color: #f8fafc;
      border: 1px solid #38bdf8;
      padding: 0.7rem 1.1rem;
      border-radius: 10px;
      font-size: 0.86rem;
      font-weight: 600;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.35);
      z-index: 50;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s ease;
    }}

    .toast.show {{
      opacity: 1;
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand-group">
      <div class="brand-icon" aria-hidden="true">A</div>
      <div>
        <h1 class="brand-title">{safe_company} — CRM de Llamadas y Tickets</h1>
        <div class="brand-sub">Línea: {safe_telnyx} · Desvío: {safe_forward}</div>
      </div>
    </div>
    <nav class="topbar-actions" aria-label="Acciones principales">
      <a href="/" class="btn">&larr; Panel Telefónico</a>
      <button type="button" id="btn-refresh" class="btn">↻ Actualizar</button>
      <a href="/api/leads/export.csv" class="btn">⬇ Exportar CSV</a>
      <button type="button" id="btn-theme" class="btn" aria-label="Cambiar tema visual">🌓 Tema: Auto</button>
    </nav>
  </header>

  <main class="container">
    <!-- KPI Summary Strip -->
    <section class="kpi-grid" aria-label="Resumen de métricas">
      <button type="button" class="kpi-card" data-kpi="all" aria-pressed="true">
        <span class="kpi-label">Total Llamadas</span>
        <span class="kpi-value" id="kpi-total">—</span>
        <span class="kpi-hint">Ver todos los registros</span>
      </button>
      <button type="button" class="kpi-card" data-kpi="pending" aria-pressed="false">
        <span class="kpi-label">Pendientes de Atención</span>
        <span class="kpi-value" id="kpi-pending">—</span>
        <span class="kpi-hint">Estado Nuevo o En Progreso</span>
      </button>
      <button type="button" class="kpi-card" data-kpi="priority" aria-pressed="false">
        <span class="kpi-label">Emergencias / Urgentes</span>
        <span class="kpi-value" id="kpi-priority">—</span>
        <span class="kpi-hint">Prioridad alta de despacho</span>
      </button>
      <button type="button" class="kpi-card" data-kpi="complete" aria-pressed="false">
        <span class="kpi-label">Con Datos de Cliente</span>
        <span class="kpi-value" id="kpi-complete">—</span>
        <span class="kpi-hint">Incluyen nombre o dirección</span>
      </button>
    </section>

    <!-- Search & Filters -->
    <section class="filters-card" aria-label="Filtros y búsqueda">
      <div class="filters-row">
        <div class="field">
          <label for="search-input">Buscar cliente, dirección, teléfono o problema</label>
          <input type="search" id="search-input" placeholder="Ej: Orlando, Julian, 407, siren, beeping..." autocomplete="off">
        </div>
        <div class="field">
          <label for="date-preset">Fecha</label>
          <select id="date-preset">
            <option value="all">Todas las fechas</option>
            <option value="today">Hoy</option>
            <option value="7d">Últimos 7 días</option>
            <option value="30d">Últimos 30 días</option>
            <option value="custom">Rango personalizado</option>
          </select>
        </div>
        <div class="field">
          <label for="filter-status">Estado CRM</label>
          <select id="filter-status">
            <option value="all">Todos los estados</option>
            <option value="nuevo">Nuevo</option>
            <option value="en_progreso">En Progreso</option>
            <option value="agendado">Agendado</option>
            <option value="resuelto">Resuelto</option>
            <option value="descartado">Descartado</option>
          </select>
        </div>
        <div class="field">
          <label for="filter-urgency">Urgencia</label>
          <select id="filter-urgency">
            <option value="all">Todas</option>
            <option value="emergency">Emergencia</option>
            <option value="urgent">Urgente</option>
            <option value="normal">Normal</option>
          </select>
        </div>
        <div class="field">
          <label for="quick-sort">Ordenar por</label>
          <select id="quick-sort">
            <option value="1:descending">Fecha (Más recientes)</option>
            <option value="1:ascending">Fecha (Más antiguas)</option>
            <option value="0:ascending">Nombre (A &rarr; Z)</option>
            <option value="0:descending">Nombre (Z &rarr; A)</option>
            <option value="3:ascending">Dirección (A &rarr; Z)</option>
            <option value="3:descending">Dirección (Z &rarr; A)</option>
            <option value="5:descending">Urgencia (Mayor primero)</option>
          </select>
        </div>
      </div>

      <div id="custom-dates-row" class="custom-dates">
        <div class="field">
          <label for="date-from">Desde</label>
          <input type="date" id="date-from">
        </div>
        <div class="field">
          <label for="date-to">Hasta</label>
          <input type="date" id="date-to">
        </div>
      </div>

      <div class="filters-footer">
        <label class="checkbox-label">
          <input type="checkbox" id="hide-empty-tests">
          Solo llamadas con datos reales (ocultar pruebas y colgadas vacías)
        </label>
        <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
          <span class="results-meta" id="results-count">Cargando llamadas...</span>
          <button type="button" id="btn-clear-filters" class="btn btn-icon">Limpiar filtros</button>
        </div>
      </div>
    </section>

    <!-- Visually hidden status announcer (for sort & filter updates) -->
    <div id="table-status" role="status" class="sr-only"></div>

    <!-- Responsive Sortable Data Table -->
    <section class="table-card">
      <div tabindex="0" role="region" aria-labelledby="leads-table-caption" class="table-wrapper">
        <table id="leads-table">
          <caption id="leads-table-caption">Registro CRM de llamadas y tickets de servicio ({safe_company})</caption>
          <thead>
            <tr>
              <th scope="col" data-type="text">
                <button type="button" commandfor="leads-table" command="--sort">
                  <span>Cliente</span><span class="sort-icon" aria-hidden="true"></span>
                </button>
              </th>
              <th scope="col" data-type="number" aria-sort="descending">
                <button type="button" commandfor="leads-table" command="--sort">
                  <span>Fecha</span><span class="sort-icon" aria-hidden="true"></span>
                </button>
              </th>
              <th scope="col">Teléfono</th>
              <th scope="col" data-type="text">
                <button type="button" commandfor="leads-table" command="--sort">
                  <span>Dirección</span><span class="sort-icon" aria-hidden="true"></span>
                </button>
              </th>
              <th scope="col">Problema / Sistema</th>
              <th scope="col" data-type="number">
                <button type="button" commandfor="leads-table" command="--sort">
                  <span>Urgencia</span><span class="sort-icon" aria-hidden="true"></span>
                </button>
              </th>
              <th scope="col" data-type="text">
                <button type="button" commandfor="leads-table" command="--sort">
                  <span>Estado CRM</span><span class="sort-icon" aria-hidden="true"></span>
                </button>
              </th>
              <th scope="col" data-type="number">
                <button type="button" commandfor="leads-table" command="--sort">
                  <span>Duración</span><span class="sort-icon" aria-hidden="true"></span>
                </button>
              </th>
              <th scope="col">Acciones</th>
            </tr>
          </thead>
          <tbody id="leads-tbody"></tbody>
        </table>
        <div id="empty-state" class="empty-state" hidden>
          No se encontraron llamadas que coincidan con los filtros actuales.
        </div>
      </div>
    </section>
  </main>

  <!-- Native Modal Dialog: Lead Detail & Transcript -->
  <dialog id="lead-detail-dialog" closedby="any" aria-labelledby="detail-title">
    <div class="dialog-header">
      <h1 id="detail-title">Detalle de Llamada</h1>
      <form method="dialog">
        <button type="submit" class="btn btn-icon" aria-label="Cerrar detalle">✕ Cerrar</button>
      </form>
    </div>
    <div class="dialog-body">
      <div class="detail-grid">
        <div class="detail-box">
          <div class="detail-box-label">Cliente</div>
          <div class="detail-box-val" id="d-name">—</div>
        </div>
        <div class="detail-box">
          <div class="detail-box-label">Teléfono de Contacto</div>
          <div class="detail-box-val" id="d-phone">—</div>
        </div>
        <div class="detail-box">
          <div class="detail-box-label">Dirección de Servicio</div>
          <div class="detail-box-val" id="d-address">—</div>
        </div>
        <div class="detail-box">
          <div class="detail-box-label">Fecha y Duración</div>
          <div class="detail-box-val" id="d-meta">—</div>
        </div>
      </div>

      <div class="summary-box">
        <div class="detail-box-label" style="color:var(--brand);">Resumen Ejecutivo IA</div>
        <div id="d-summary">—</div>
      </div>

      <div class="detail-box">
        <div class="detail-box-label">Problema Reportado</div>
        <div class="detail-box-val" id="d-issue">—</div>
      </div>

      <div class="crm-edit-grid">
        <div class="field">
          <label for="d-status">Estado CRM</label>
          <select id="d-status" class="detail-select">
            <option value="nuevo">Nuevo</option>
            <option value="en_progreso">En Progreso</option>
            <option value="agendado">Agendado</option>
            <option value="resuelto">Resuelto</option>
            <option value="descartado">Descartado</option>
          </select>
        </div>
        <div class="field">
          <label for="d-urgency">Urgencia</label>
          <select id="d-urgency" class="detail-select">
            <option value="emergency">Emergencia</option>
            <option value="urgent">Urgente</option>
            <option value="normal">Normal</option>
          </select>
        </div>
      </div>

      <div class="field">
        <label for="d-notes">Notas del Supervisor / Técnico</label>
        <textarea id="d-notes" class="detail-textarea" placeholder="Ej: Se llamó al cliente, técnico asignado para mañana 10:00 AM..."></textarea>
      </div>

      <div>
        <div class="detail-box-label" style="margin-bottom:0.45rem;">Transcripción Completa de la Llamada</div>
        <div id="d-transcript" class="transcript-list"></div>
      </div>
    </div>
    <div class="dialog-footer">
      <button type="button" id="btn-save-lead" class="btn btn-primary" autofocus>Guardar Cambios</button>
      <form method="dialog">
        <button type="submit" class="btn">Cerrar</button>
      </form>
    </div>
  </dialog>

  <!-- Native Modal Dialog: Delete Confirmation -->
  <dialog id="delete-confirm-dialog" aria-labelledby="delete-title">
    <div class="dialog-header">
      <h1 id="delete-title">Eliminar registro</h1>
    </div>
    <div class="dialog-body">
      <p id="delete-message" style="margin:0;">¿Seguro que deseas eliminar esta llamada del CRM? Esta acción no se puede deshacer.</p>
    </div>
    <div class="dialog-footer">
      <form method="dialog" style="display:flex;gap:0.6rem;">
        <button type="submit" value="cancel" class="btn" autofocus>Cancelar</button>
        <button type="submit" value="delete" class="btn btn-danger">Eliminar</button>
      </form>
    </div>
  </dialog>

  <div id="toast" class="toast" role="status" aria-live="polite"></div>

  <script>
    const table = document.getElementById('leads-table');
    const tbody = document.getElementById('leads-tbody');
    const emptyState = document.getElementById('empty-state');
    const tableStatus = document.getElementById('table-status');
    const resultsCount = document.getElementById('results-count');
    const detailDialog = document.getElementById('lead-detail-dialog');
    const deleteDialog = document.getElementById('delete-confirm-dialog');
    const toastEl = document.getElementById('toast');

    const collator = new Intl.Collator('es', {{ numeric: true, sensitivity: 'base' }});
    const dateFormatter = new Intl.DateTimeFormat('es', {{
      year: 'numeric', month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    }});

    const URGENCY_RANK = {{ emergency: 3, urgent: 2, normal: 1 }};
    const URGENCY_LABELS = {{ emergency: '🚨 Emergencia', urgent: '⚠️ Urgente', normal: '● Normal' }};
    const SYSTEM_LABELS = {{
      fire_alarm: 'Alarma Incendio',
      burglar_alarm: 'Alarma Intrusión',
      cctv_security: 'CCTV / Seguridad',
      other: 'Sistema Alarma',
      unknown: 'Sin clasificar'
    }};

    let leadsById = new Map();
    let activeLeadId = null;
    let pendingDeleteId = null;
    let activeKpiFilter = 'all';
    let currentSort = {{ col: 1, dir: 'descending' }};

    function showToast(msg) {{
      toastEl.textContent = msg;
      toastEl.classList.add('show');
      clearTimeout(showToast._timer);
      showToast._timer = setTimeout(() => toastEl.classList.remove('show'), 2600);
    }}

    function parseUtcTimestamp(ts) {{
      if (!ts) return 0;
      const iso = ts.includes('T') ? ts : ts.replace(' ', 'T') + 'Z';
      const ms = Date.parse(iso);
      return Number.isNaN(ms) ? 0 : ms;
    }}

    function formatDuration(sec) {{
      const total = Math.max(0, Math.round(Number(sec) || 0));
      const m = Math.floor(total / 60);
      const s = total % 60;
      return m > 0 ? `${{m}}m ${{String(s).padStart(2, '0')}}s` : `${{s}}s`;
    }}

    function initialsFor(name) {{
      if (!name) return '?';
      const parts = name.trim().split(/\\s+/).slice(0, 2);
      return parts.map(p => p[0]?.toUpperCase() || '').join('') || '?';
    }}

    function isTestOrEmpty(lead) {{
      const sid = (lead.call_sid || '').toUpperCase();
      const hasInfo = Boolean((lead.caller_name && lead.caller_name.trim()) || (lead.service_address && lead.service_address.trim()) || (lead.issue_description && lead.issue_description.trim()));
      if (sid.startsWith('TEST')) return true;
      if (!hasInfo && (Number(lead.duration_seconds) || 0) < 15) return true;
      return false;
    }}

    function buildRow(lead) {{
      const tr = document.createElement('tr');
      tr.dataset.id = String(lead.id);

      const tsMs = parseUtcTimestamp(lead.timestamp);
      const displayName = (lead.caller_name || '').trim() || 'Sin nombre';
      const phone = (lead.caller_phone || lead.caller_from_number || '').trim() || 'Desconocido';
      const address = (lead.service_address || '').trim() || 'Sin dirección';
      const issue = (lead.issue_description || lead.reason_for_call || lead.summary || '').trim() || 'Sin descripción';
      const sysType = SYSTEM_LABELS[lead.system_type] || SYSTEM_LABELS.unknown;
      const urgency = (lead.urgency || 'normal').toLowerCase();
      const status = (lead.status || 'nuevo').toLowerCase();
      const duration = Number(lead.duration_seconds) || 0;

      // Col 0: Sticky Row Header (Client Name)
      const th = document.createElement('th');
      th.scope = 'row';
      th.dataset.value = displayName.toLowerCase();
      const clientWrap = document.createElement('div');
      clientWrap.className = 'client-cell';
      const avatar = document.createElement('span');
      avatar.className = 'avatar';
      avatar.setAttribute('aria-hidden', 'true');
      avatar.textContent = initialsFor(lead.caller_name);
      const infoDiv = document.createElement('div');
      const nameSpan = document.createElement('span');
      nameSpan.className = 'client-name';
      nameSpan.textContent = displayName;
      nameSpan.title = displayName;
      const subSpan = document.createElement('span');
      subSpan.className = 'client-sub';
      subSpan.textContent = `#${{lead.id}}`;
      infoDiv.append(nameSpan, subSpan);
      clientWrap.append(avatar, infoDiv);
      th.appendChild(clientWrap);

      // Col 1: Date
      const tdDate = document.createElement('td');
      tdDate.dataset.value = String(tsMs);
      const timeEl = document.createElement('time');
      timeEl.dateTime = lead.timestamp || '';
      timeEl.textContent = tsMs ? dateFormatter.format(new Date(tsMs)) : '—';
      tdDate.appendChild(timeEl);

      // Col 2: Phone
      const tdPhone = document.createElement('td');
      if (phone !== 'Desconocido') {{
        const a = document.createElement('a');
        a.className = 'phone-link';
        a.href = `tel:${{phone.replace(/[^\\d+]/g, '')}}`;
        a.textContent = phone;
        tdPhone.appendChild(a);
      }} else {{
        tdPhone.textContent = phone;
      }}

      // Col 3: Address
      const tdAddr = document.createElement('td');
      tdAddr.dataset.value = address.toLowerCase();
      const addrSpan = document.createElement('span');
      addrSpan.className = 'addr-text';
      addrSpan.textContent = address;
      addrSpan.title = address;
      tdAddr.appendChild(addrSpan);

      // Col 4: Issue / System
      const tdIssue = document.createElement('td');
      const issueSpan = document.createElement('span');
      issueSpan.className = 'issue-text';
      issueSpan.textContent = issue;
      issueSpan.title = issue;
      const sysSpan = document.createElement('span');
      sysSpan.className = 'sys-tag';
      sysSpan.textContent = sysType;
      tdIssue.append(issueSpan, sysSpan);

      // Col 5: Urgency
      const tdUrg = document.createElement('td');
      tdUrg.dataset.value = String(URGENCY_RANK[urgency] || 1);
      const pill = document.createElement('span');
      pill.className = `pill pill-${{urgency in URGENCY_RANK ? urgency : 'normal'}}`;
      pill.textContent = URGENCY_LABELS[urgency] || URGENCY_LABELS.normal;
      tdUrg.appendChild(pill);

      // Col 6: CRM Status (inline editable)
      const tdStatus = document.createElement('td');
      tdStatus.dataset.value = status;
      const sel = document.createElement('select');
      sel.className = 'status-select';
      sel.dataset.status = status;
      sel.setAttribute('aria-label', `Estado del ticket #${{lead.id}}`);
      for (const [val, label] of [
        ['nuevo', 'Nuevo'],
        ['en_progreso', 'En Progreso'],
        ['agendado', 'Agendado'],
        ['resuelto', 'Resuelto'],
        ['descartado', 'Descartado']
      ]) {{
        const opt = document.createElement('option');
        opt.value = val;
        opt.textContent = label;
        if (val === status) opt.selected = true;
        sel.appendChild(opt);
      }}
      sel.addEventListener('change', async () => {{
        const newStatus = sel.value;
        sel.dataset.status = newStatus;
        tdStatus.dataset.value = newStatus;
        await patchLead(lead.id, {{ status: newStatus }});
      }});
      tdStatus.appendChild(sel);

      // Col 7: Duration
      const tdDur = document.createElement('td');
      tdDur.dataset.value = String(duration);
      tdDur.textContent = formatDuration(duration);

      // Col 8: Actions
      const tdAct = document.createElement('td');
      const actWrap = document.createElement('div');
      actWrap.className = 'actions-cell';
      const btnDetail = document.createElement('button');
      btnDetail.type = 'button';
      btnDetail.className = 'btn btn-icon';
      btnDetail.textContent = 'Ver ficha';
      btnDetail.addEventListener('click', () => openDetailModal(lead.id));

      const btnDel = document.createElement('button');
      btnDel.type = 'button';
      btnDel.className = 'btn btn-icon';
      btnDel.textContent = '🗑';
      btnDel.title = 'Eliminar llamada';
      btnDel.setAttribute('aria-label', `Eliminar llamada #${{lead.id}}`);
      btnDel.addEventListener('click', () => {{
        pendingDeleteId = lead.id;
        document.getElementById('delete-message').textContent =
          `¿Seguro que deseas eliminar el ticket #${{lead.id}} (${{displayName}})? Esta acción no se puede deshacer.`;
        deleteDialog.showModal();
      }});
      actWrap.append(btnDetail, btnDel);
      tdAct.appendChild(actWrap);

      tr.append(th, tdDate, tdPhone, tdAddr, tdIssue, tdUrg, tdStatus, tdDur, tdAct);
      return tr;
    }}

    function updateKPIs() {{
      const all = [...leadsById.values()];
      const pending = all.filter(l => ['nuevo', 'en_progreso'].includes((l.status || 'nuevo').toLowerCase())).length;
      const priority = all.filter(l => ['emergency', 'urgent'].includes((l.urgency || 'normal').toLowerCase())).length;
      const complete = all.filter(l => Boolean((l.caller_name && l.caller_name.trim()) || (l.service_address && l.service_address.trim()))).length;
      document.getElementById('kpi-total').textContent = String(all.length);
      document.getElementById('kpi-pending').textContent = String(pending);
      document.getElementById('kpi-priority').textContent = String(priority);
      document.getElementById('kpi-complete').textContent = String(complete);
    }}

    function applyFilters() {{
      const query = document.getElementById('search-input').value.trim().toLowerCase();
      const datePreset = document.getElementById('date-preset').value;
      const statusFilter = document.getElementById('filter-status').value;
      const urgencyFilter = document.getElementById('filter-urgency').value;
      const hideEmpty = document.getElementById('hide-empty-tests').checked;
      const fromVal = document.getElementById('date-from').value;
      const toVal = document.getElementById('date-to').value;

      const now = new Date();
      let minMs = 0;
      let maxMs = Infinity;
      if (datePreset === 'today') {{
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        minMs = start.getTime();
      }} else if (datePreset === '7d') {{
        minMs = Date.now() - 7 * 86400000;
      }} else if (datePreset === '30d') {{
        minMs = Date.now() - 30 * 86400000;
      }} else if (datePreset === 'custom') {{
        if (fromVal) minMs = new Date(fromVal + 'T00:00:00').getTime();
        if (toVal) maxMs = new Date(toVal + 'T23:59:59.999').getTime();
      }}

      let visibleCount = 0;
      for (const tr of tbody.rows) {{
        const lead = leadsById.get(Number(tr.dataset.id));
        if (!lead) continue;
        let visible = true;

        if (hideEmpty && isTestOrEmpty(lead)) visible = false;

        if (visible && activeKpiFilter === 'pending') {{
          visible = ['nuevo', 'en_progreso'].includes((lead.status || 'nuevo').toLowerCase());
        }} else if (visible && activeKpiFilter === 'priority') {{
          visible = ['emergency', 'urgent'].includes((lead.urgency || 'normal').toLowerCase());
        }} else if (visible && activeKpiFilter === 'complete') {{
          visible = Boolean((lead.caller_name && lead.caller_name.trim()) || (lead.service_address && lead.service_address.trim()));
        }}

        if (visible && statusFilter !== 'all') {{
          visible = (lead.status || 'nuevo').toLowerCase() === statusFilter;
        }}
        if (visible && urgencyFilter !== 'all') {{
          visible = (lead.urgency || 'normal').toLowerCase() === urgencyFilter;
        }}
        if (visible) {{
          const tsMs = parseUtcTimestamp(lead.timestamp);
          if (tsMs < minMs || tsMs > maxMs) visible = false;
        }}
        if (visible && query) {{
          const transcriptText = Array.isArray(lead.transcript)
            ? lead.transcript.map(t => t.content || '').join(' ')
            : '';
          const haystack = [
            lead.caller_name, lead.caller_phone, lead.caller_from_number,
            lead.service_address, lead.issue_description, lead.summary,
            lead.notes, lead.call_sid, transcriptText
          ].filter(Boolean).join(' ').toLowerCase();
          visible = haystack.includes(query);
        }}

        tr.hidden = !visible;
        if (visible) visibleCount++;
      }}

      emptyState.hidden = visibleCount > 0;
      resultsCount.textContent = `Mostrando ${{visibleCount}} de ${{leadsById.size}} llamadas`;
      tableStatus.textContent = `Mostrando ${{visibleCount}} llamadas`;
    }}

    // Accessible in-place DOM reordering (never rebuilds tbody with innerHTML)
    function reorderRowsInPlace(orderedRows) {{
      const doMove = () => {{
        for (const row of orderedRows) {{
          if (typeof tbody.moveBefore === 'function') {{
            tbody.moveBefore(row, null);
          }} else {{
            tbody.appendChild(row);
          }}
        }}
      }};
      if (typeof table.startViewTransition === 'function' && orderedRows.length <= 80) {{
        table.startViewTransition(doMove);
      }} else {{
        doMove();
      }}
    }}

    function sortTableByColumn(colIndex, direction, announceLabel) {{
      const headerCells = table.tHead.rows[0].cells;
      const th = headerCells[colIndex];
      if (!th) return;
      const type = th.dataset.type || 'text';

      for (const h of headerCells) h.removeAttribute('aria-sort');
      th.setAttribute('aria-sort', direction);
      currentSort = {{ col: colIndex, dir: direction }};

      const quickSortEl = document.getElementById('quick-sort');
      const key = `${{colIndex}}:${{direction}}`;
      if ([...quickSortEl.options].some(o => o.value === key)) {{
        quickSortEl.value = key;
      }}

      const factor = direction === 'ascending' ? 1 : -1;
      const rows = [...tbody.rows];
      const keyed = rows.map(row => {{
        const cell = row.cells[colIndex];
        const raw = cell.dataset.value ?? cell.textContent.trim();
        return {{ row, val: type === 'number' ? Number(raw) : raw }};
      }});

      keyed.sort((a, b) =>
        factor * (type === 'number' ? (a.val - b.val) : collator.compare(a.val, b.val))
      );

      reorderRowsInPlace(keyed.map(k => k.row));
      if (announceLabel) {{
        tableStatus.textContent = `Ordenado por ${{announceLabel}}, ${{direction === 'ascending' ? 'ascendente' : 'descendente'}}, ${{rows.length}} filas`;
      }}
    }}

    function handleHeaderSort(button) {{
      const th = button.closest('th');
      if (!th) return;
      const nextDir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
      sortTableByColumn(th.cellIndex, nextDir, button.textContent.trim());
    }}

    // Invoker commands listener + feature-detected fallback (never double-fires)
    table.addEventListener('command', (event) => {{
      if (event.command === '--sort' && event.source) {{
        handleHeaderSort(event.source);
      }}
    }});

    if (!('commandForElement' in HTMLButtonElement.prototype)) {{
      for (const button of table.tHead.querySelectorAll('button[command="--sort"]')) {{
        button.addEventListener('click', () => handleHeaderSort(button));
      }}
    }}

    // Safari / fallback for closedby="any" light dismiss
    if (!('closedBy' in HTMLDialogElement.prototype)) {{
      const isOutside = (e, dlg) => {{
        const r = dlg.getBoundingClientRect();
        return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
      }};
      for (const dlg of document.querySelectorAll('dialog[closedby="any"]')) {{
        let pressedOutside = false;
        dlg.addEventListener('pointerdown', (e) => {{ pressedOutside = isOutside(e, dlg); }});
        dlg.addEventListener('pointerup', (e) => {{
          if (pressedOutside && isOutside(e, dlg)) dlg.close();
        }});
      }}
    }}

    function openDetailModal(id) {{
      const lead = leadsById.get(id);
      if (!lead) return;
      activeLeadId = id;

      const name = (lead.caller_name || '').trim() || 'Cliente sin nombre';
      const phone = (lead.caller_phone || lead.caller_from_number || '').trim() || 'No registrado';
      const address = (lead.service_address || '').trim() || 'No registrada';
      const tsMs = parseUtcTimestamp(lead.timestamp);

      document.getElementById('detail-title').textContent = `Ticket #${{lead.id}} — ${{name}}`;
      document.getElementById('d-name').textContent = name;

      const dPhone = document.getElementById('d-phone');
      dPhone.replaceChildren();
      if (phone !== 'No registrado') {{
        const a = document.createElement('a');
        a.className = 'phone-link';
        a.href = `tel:${{phone.replace(/[^\\d+]/g, '')}}`;
        a.textContent = phone;
        const copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'btn btn-icon';
        copyBtn.style.marginLeft = '0.5rem';
        copyBtn.textContent = 'Copiar';
        copyBtn.addEventListener('click', () => {{
          navigator.clipboard?.writeText(phone);
          showToast('Teléfono copiado al portapapeles');
        }});
        dPhone.append(a, copyBtn);
      }} else {{
        dPhone.textContent = phone;
      }}

      const dAddr = document.getElementById('d-address');
      dAddr.replaceChildren();
      dAddr.append(document.createTextNode(address));
      if (address !== 'No registrada') {{
        const mapLink = document.createElement('a');
        mapLink.href = `https://www.google.com/maps/search/?api=1&query=${{encodeURIComponent(address)}}`;
        mapLink.target = '_blank';
        mapLink.rel = 'noopener noreferrer';
        mapLink.className = 'btn btn-icon';
        mapLink.style.marginLeft = '0.5rem';
        mapLink.textContent = '📍 Mapa';
        dAddr.appendChild(mapLink);
      }}

      document.getElementById('d-meta').textContent =
        `${{tsMs ? dateFormatter.format(new Date(tsMs)) : '—'}} · ${{formatDuration(lead.duration_seconds)}} · ${{SYSTEM_LABELS[lead.system_type] || 'Alarma'}}`;
      document.getElementById('d-summary').textContent = lead.summary || 'Sin resumen generado.';
      document.getElementById('d-issue').textContent = lead.issue_description || lead.reason_for_call || 'Sin descripción registrada.';
      document.getElementById('d-status').value = (lead.status || 'nuevo').toLowerCase();
      document.getElementById('d-urgency').value = (lead.urgency || 'normal').toLowerCase();
      document.getElementById('d-notes').value = lead.notes || '';

      const txContainer = document.getElementById('d-transcript');
      txContainer.replaceChildren();
      const tx = Array.isArray(lead.transcript) ? lead.transcript : [];
      if (tx.length === 0) {{
        const p = document.createElement('p');
        p.style.margin = '0';
        p.style.color = 'var(--text-muted)';
        p.textContent = 'No hay transcripción disponible para esta llamada.';
        txContainer.appendChild(p);
      }} else {{
        for (const turn of tx) {{
          const role = (turn.role || 'assistant').toLowerCase();
          const div = document.createElement('div');
          div.className = `bubble ${{role === 'caller' ? 'bubble-caller' : 'bubble-assistant'}}`;
          const rSpan = document.createElement('span');
          rSpan.className = 'bubble-role';
          rSpan.textContent = role === 'caller' ? 'Cliente' : 'Recepcionista IA';
          const cSpan = document.createElement('span');
          cSpan.textContent = turn.content || '';
          div.append(rSpan, cSpan);
          txContainer.appendChild(div);
        }}
      }}

      detailDialog.showModal();
    }}

    async function patchLead(id, payload) {{
      try {{
        const res = await fetch(`/api/leads/${{id}}`, {{
          method: 'PATCH',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payload)
        }});
        if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
        const updated = await res.json();
        leadsById.set(id, updated);
        updateKPIs();
        showToast(`Ticket #${{id}} actualizado`);
        return updated;
      }} catch (err) {{
        showToast('Error al guardar cambios');
        console.error(err);
      }}
    }}

    document.getElementById('btn-save-lead').addEventListener('click', async () => {{
      if (activeLeadId == null) return;
      const payload = {{
        status: document.getElementById('d-status').value,
        urgency: document.getElementById('d-urgency').value,
        notes: document.getElementById('d-notes').value
      }};
      const updated = await patchLead(activeLeadId, payload);
      if (updated) {{
        const existingRow = tbody.querySelector(`tr[data-id="${{activeLeadId}}"]`);
        if (existingRow) {{
          existingRow.replaceWith(buildRow(updated));
          sortTableByColumn(currentSort.col, currentSort.dir, null);
          applyFilters();
        }}
        detailDialog.close();
      }}
    }});

    deleteDialog.addEventListener('close', async () => {{
      const choice = deleteDialog.returnValue;
      deleteDialog.returnValue = '';
      if (choice === 'delete' && pendingDeleteId != null) {{
        const id = pendingDeleteId;
        pendingDeleteId = null;
        try {{
          const res = await fetch(`/api/leads/${{id}}`, {{ method: 'DELETE' }});
          if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
          leadsById.delete(id);
          tbody.querySelector(`tr[data-id="${{id}}"]`)?.remove();
          updateKPIs();
          applyFilters();
          showToast(`Ticket #${{id}} eliminado`);
        }} catch (err) {{
          showToast('Error al eliminar registro');
          console.error(err);
        }}
      }} else {{
        pendingDeleteId = null;
      }}
    }});

    async function loadLeads() {{
      resultsCount.textContent = 'Actualizando datos...';
      try {{
        const res = await fetch('/api/leads?limit=500');
        const data = await res.json();
        leadsById.clear();
        const frag = document.createDocumentFragment();
        for (const lead of (data.leads || [])) {{
          leadsById.set(lead.id, lead);
          frag.appendChild(buildRow(lead));
        }}
        tbody.replaceChildren(frag);
        updateKPIs();
        sortTableByColumn(currentSort.col, currentSort.dir, null);
        applyFilters();
      }} catch (err) {{
        resultsCount.textContent = 'Error cargando llamadas';
        console.error(err);
      }}
    }}

    // Event bindings for filters, KPIs, sort dropdown, and theme
    document.getElementById('search-input').addEventListener('input', applyFilters);
    document.getElementById('filter-status').addEventListener('change', applyFilters);
    document.getElementById('filter-urgency').addEventListener('change', applyFilters);
    document.getElementById('hide-empty-tests').addEventListener('change', applyFilters);
    document.getElementById('date-from').addEventListener('change', applyFilters);
    document.getElementById('date-to').addEventListener('change', applyFilters);

    document.getElementById('date-preset').addEventListener('change', (e) => {{
      document.getElementById('custom-dates-row').classList.toggle('visible', e.target.value === 'custom');
      applyFilters();
    }});

    document.getElementById('quick-sort').addEventListener('change', (e) => {{
      const [col, dir] = e.target.value.split(':');
      sortTableByColumn(Number(col), dir, e.target.selectedOptions[0]?.textContent || '');
    }});

    for (const card of document.querySelectorAll('.kpi-card')) {{
      card.addEventListener('click', () => {{
        activeKpiFilter = card.dataset.kpi;
        for (const c of document.querySelectorAll('.kpi-card')) {{
          c.setAttribute('aria-pressed', String(c === card));
        }}
        applyFilters();
      }});
    }}

    document.getElementById('btn-clear-filters').addEventListener('click', () => {{
      document.getElementById('search-input').value = '';
      document.getElementById('date-preset').value = 'all';
      document.getElementById('custom-dates-row').classList.remove('visible');
      document.getElementById('date-from').value = '';
      document.getElementById('date-to').value = '';
      document.getElementById('filter-status').value = 'all';
      document.getElementById('filter-urgency').value = 'all';
      document.getElementById('hide-empty-tests').checked = false;
      activeKpiFilter = 'all';
      for (const c of document.querySelectorAll('.kpi-card')) {{
        c.setAttribute('aria-pressed', String(c.dataset.kpi === 'all'));
      }}
      applyFilters();
    }});

    document.getElementById('btn-refresh').addEventListener('click', loadLeads);

    // Theme toggle (Auto / Dark / Light)
    const themeBtn = document.getElementById('btn-theme');
    const THEMES = ['auto', 'dark', 'light'];
    const THEME_LABELS = {{ auto: '🌓 Tema: Auto', dark: '🌙 Tema: Oscuro', light: '☀️ Tema: Claro' }};
    function applyTheme(t) {{
      if (t === 'auto') {{
        document.documentElement.removeAttribute('data-theme');
      }} else {{
        document.documentElement.setAttribute('data-theme', t);
      }}
      themeBtn.textContent = THEME_LABELS[t] || THEME_LABELS.auto;
      try {{ localStorage.setItem('alarmtronics_theme', t); }} catch {{}}
    }}
    let savedTheme = 'auto';
    try {{ savedTheme = localStorage.getItem('alarmtronics_theme') || 'auto'; }} catch {{}}
    applyTheme(THEMES.includes(savedTheme) ? savedTheme : 'auto');
    themeBtn.addEventListener('click', () => {{
      const cur = document.documentElement.getAttribute('data-theme') || 'auto';
      const next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
      applyTheme(next);
    }});

    loadLeads();
  </script>
</body>
</html>
"""
