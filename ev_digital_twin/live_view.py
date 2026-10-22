"""Pure SVG rendering helpers for the real-time dashboard."""

import html


GREEN_DARK = "#173404"
GREEN_MID = "#3B6D11"
GREEN_LINE = "#639922"
GREEN_LIGHT = "#97C459"
GREEN_BG = "#EAF3DE"


def render_live_state(snapshot: dict) -> str:
    """Render a responsive, self-contained live digital-twin view."""
    state = snapshot.get("state", {})
    grid = state.get("grid", {})
    stations = state.get("stations", [])
    evs = state.get("evs", [])
    width, height = 470, 245
    capacity = max(float(grid.get("capacity_mw", 1.0)), 0.001)
    load = max(float(grid.get("net_load_mw", 0.0)), 0.0)
    load_ratio = min(1.0, load / capacity)
    meter_color = "#b42318" if load_ratio >= 1.0 else GREEN_MID
    ev_by_id = {ev.get("ev_id"): ev for ev in evs}
    colors = {
        "charging": GREEN_LINE,
        "v2g_discharging": "#b42318",
        "idle": "#64748b",
    }
    groups = [[] for _ in range(4)]
    for index, station in enumerate(stations):
        groups[index % 4].append(station)

    panels = []
    for group_index, group in enumerate(groups):
        station_shapes = []
        for station_index, station in enumerate(group):
            x = 16 + (station_index % 2) * 220
            y = 34 + (station_index // 2) * 82
            station_id = html.escape(str(station.get("station_id", "station")))
            station_shapes.append(
                f'<rect x="{x}" y="{y}" width="190" height="58" rx="6" '
                f'fill="{GREEN_BG}" stroke="{GREEN_LINE}"/>'
                f'<text x="{x + 8}" y="{y + 17}" font-size="11" '
                f'fill="{GREEN_DARK}">{station_id}</text>'
            )
            occupancy = station.get("occupancy", {})
            for connector in range(4):
                ev_id = occupancy.get(connector, occupancy.get(str(connector)))
                ev = ev_by_id.get(ev_id)
                color = colors.get(ev.get("state"), "#64748b") if ev else "#cbd5e1"
                soc = max(0.0, min(1.0, float(ev.get("soc", 0.0)))) if ev else 0.0
                fill_height = max(2, soc * 24) if ev else 0
                ev_x = x + 12 + connector * 28
                ev_y = y + 28
                station_shapes.append(
                    f'<rect x="{ev_x}" y="{ev_y + 24 - fill_height:.1f}" '
                    f'width="12" height="{fill_height:.1f}" fill="{color}"/>'
                    f'<rect x="{ev_x}" y="{ev_y}" width="12" height="24" '
                    f'fill="none" stroke="{color}"/>'
                )
        panels.append(
            f'<div style="width:100%;min-width:0;overflow:hidden">'
            f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
            f'aria-label="Station grid {group_index + 1}">'
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>'
            f'<text x="16" y="20" font-size="13" font-weight="600" '
            f'fill="{GREEN_DARK}">Station grid {group_index + 1}</text>'
            f'{"".join(station_shapes)}</svg></div>'
        )

    error = snapshot.get("error")
    error_markup = (
        f'<div style="color:#b42318;font-size:12px;margin-top:8px">'
        f'Live runner error: {html.escape(str(error))}</div>'
        if error else ""
    )
    status = "running" if snapshot.get("running") else "stopped"
    return f"""
    <div style="font-family:sans-serif;color:{GREEN_DARK}">
      <div style="font-size:14px;margin-bottom:6px">
        Live station layouts · {status} · t={float(state.get("time_h", 0)):.2f}h
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:12px;font-size:12px;margin-bottom:8px">
        <span>Net load <strong>{load:.2f}/{capacity:.2f} MW</strong></span>
        <span>Solar <strong>{float(grid.get("solar_mw", 0)):.2f} MW</strong></span>
        <span>V2G export <strong>{float(grid.get("v2g_export_mw", 0)):.2f} MW</strong></span>
        <span>EVs <strong>{len(evs)}</strong></span>
      </div>
      <div aria-label="Grid capacity utilization"
           style="height:8px;background:#e2e8f0;border-radius:4px;margin-bottom:8px">
        <div style="width:{100 * load_ratio:.1f}%;height:8px;background:{meter_color};
                    border-radius:4px"></div>
      </div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:11px;margin-bottom:8px">
        <span><i style="color:{GREEN_LINE}">■</i> Charging</span>
        <span><i style="color:#b42318">■</i> V2G discharge</span>
        <span><i style="color:#64748b">■</i> Idle</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
                  gap:10px;width:100%">
        {"".join(panels)}
      </div>
      {error_markup}
    </div>
    """
