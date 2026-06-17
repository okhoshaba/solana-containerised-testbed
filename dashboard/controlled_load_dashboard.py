#!/usr/bin/env python3
import math
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass

import requests
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go


def with_metrics_path(url: str) -> str:
    url = url.rstrip("/")
    return url if url.endswith("/metrics") else url + "/metrics"


PROM_URL = with_metrics_path(os.environ.get("PROM_URL", "http://127.0.0.1:9464"))
LOADGEN_BASE = os.environ.get("LOADGEN_URL", "http://127.0.0.1:7070").rstrip("/")
LOADGEN_STATS = f"{LOADGEN_BASE}/stats"
LOADGEN_RATE = f"{LOADGEN_BASE}/rate"
RATE_KEY = os.environ.get("RATE_KEY", "lambda")
TS = float(os.environ.get("DASH_SAMPLE_SECONDS", "1"))
HIST_SEC = int(os.environ.get("DASH_HISTORY_SECONDS", "600"))
N_HIST = max(10, int(HIST_SEC / TS))
Y_REF = float(os.environ.get("LATENCY_REF_SECONDS", "0.50"))
Y_MAX = float(os.environ.get("LATENCY_SLO_SECONDS", "0.80"))
SAT_BAD = float(os.environ.get("SATURATION_BAD_THRESHOLD", "0.90"))


def prom_get_quantile(text: str, metric: str, q: str):
    pat = re.compile(
        rf'^{re.escape(metric)}\{{[^}}]*quantile="{re.escape(q)}"[^}}]*\}}\s+([0-9eE+\-.]+)\s*$',
        re.M,
    )
    m = pat.search(text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def safe_get_json(url: str, timeout=0.8):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def safe_post_json(url: str, payload: dict, timeout=0.8):
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return True


def fnum(x, nd=3):
    if x is None:
        return "NaN"
    try:
        if isinstance(x, float) and math.isnan(x):
            return "NaN"
        return f"{float(x):.{nd}f}"
    except Exception:
        return "NaN"


@dataclass
class Sample:
    t: float
    lat_p99: float
    slot_p99: float
    u_cmd: float
    sent_reported: float
    sent_total: float
    u_ach: float
    sat: float
    inflight: float
    err_s: float


class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.t = deque(maxlen=N_HIST)
        self.lat = deque(maxlen=N_HIST)
        self.slot = deque(maxlen=N_HIST)
        self.u_cmd = deque(maxlen=N_HIST)
        self.sent_reported = deque(maxlen=N_HIST)
        self.sent_total = deque(maxlen=N_HIST)
        self.u_ach = deque(maxlen=N_HIST)
        self.sat = deque(maxlen=N_HIST)
        self.inflight = deque(maxlen=N_HIST)
        self.err_s = deque(maxlen=N_HIST)
        self.last_ok = True
        self.last_err = ""
        self.current_cmd = 20.0
        self._prev_sent_total = None
        self._prev_wall = None

    def push(self, s: Sample):
        with self.lock:
            self.t.append(s.t)
            self.lat.append(s.lat_p99)
            self.slot.append(s.slot_p99)
            self.u_cmd.append(s.u_cmd)
            self.sent_reported.append(s.sent_reported)
            self.sent_total.append(s.sent_total)
            self.u_ach.append(s.u_ach)
            self.sat.append(s.sat)
            self.inflight.append(s.inflight)
            self.err_s.append(s.err_s)

    def snapshot(self):
        with self.lock:
            return {
                "t": list(self.t),
                "lat": list(self.lat),
                "slot": list(self.slot),
                "u_cmd": list(self.u_cmd),
                "sent_reported": list(self.sent_reported),
                "sent_total": list(self.sent_total),
                "u_ach": list(self.u_ach),
                "sat": list(self.sat),
                "inflight": list(self.inflight),
                "err_s": list(self.err_s),
                "last_ok": self.last_ok,
                "last_err": self.last_err,
                "current_cmd": self.current_cmd,
            }

    def calc_u_ach(self, sent_total: float, wall_time: float):
        if self._prev_sent_total is None or self._prev_wall is None:
            self._prev_sent_total = sent_total
            self._prev_wall = wall_time
            return float("nan")
        dt = wall_time - self._prev_wall
        ds = sent_total - self._prev_sent_total
        self._prev_sent_total = sent_total
        self._prev_wall = wall_time
        if dt <= 0:
            return float("nan")
        return ds / dt


STATE = SharedState()


def poll_loop():
    t0 = time.time()
    while True:
        tnow = time.time() - t0
        try:
            prom = requests.get(PROM_URL, timeout=0.8)
            prom.raise_for_status()
            text = prom.text
            lat_p99 = prom_get_quantile(text, "solana_transaction_latency_seconds", "0.99")
            slot_p99 = prom_get_quantile(text, "solana_slot_interval_seconds", "0.99")
            lat_p99 = float("nan") if lat_p99 is None else lat_p99
            slot_p99 = float("nan") if slot_p99 is None else slot_p99

            st = safe_get_json(LOADGEN_STATS, timeout=0.8)
            u_cmd = float(st.get("target_lambda", STATE.current_cmd))
            sent_reported = float(st.get("sent_per_sec", 0.0))
            sent_total = float(st.get("sent_total", float("nan")))
            infl = float(st.get("inflight", 0.0))
            err_s = float(st.get("err_per_sec", 0.0))
            wall = time.time()
            u_ach = STATE.calc_u_ach(sent_total, wall)
            sat = u_ach / u_cmd if u_cmd > 0 and not (isinstance(u_ach, float) and math.isnan(u_ach)) else float("nan")
            STATE.last_ok = True
            STATE.last_err = ""
            STATE.push(Sample(tnow, lat_p99, slot_p99, u_cmd, sent_reported, sent_total, u_ach, sat, infl, err_s))
        except Exception as e:
            STATE.last_ok = False
            STATE.last_err = str(e)
        time.sleep(TS)


app = Dash(__name__)
app.title = "Solana Controlled Load Dashboard"
app.layout = html.Div(
    style={"maxWidth": "1250px", "margin": "0 auto", "fontFamily": "sans-serif"},
    children=[
        html.H2("Solana Controlled Load Dashboard: target throughput, achieved throughput and latency"),
        html.Div(
            style={"display": "flex", "gap": "16px", "alignItems": "center", "flexWrap": "wrap"},
            children=[
                html.Div([html.Div("lambda_target, tx/s"), dcc.Input(id="inp_lambda", type="number", value=20, step=10, min=0, style={"width": "130px"})]),
                html.Button("Apply target", id="btn_apply", n_clicks=0),
                html.Div([html.Div("Latency reference, sec"), dcc.Input(id="inp_yref", type="number", value=Y_REF, step=0.05, min=0, style={"width": "130px"})]),
                html.Div([html.Div("Latency SLO, sec"), dcc.Input(id="inp_ymax", type="number", value=Y_MAX, step=0.05, min=0, style={"width": "130px"})]),
                html.Div(id="sat_badge", style={"padding": "6px 10px", "borderRadius": "10px", "fontWeight": "600"}),
                html.Div(id="status_line", style={"marginLeft": "12px", "fontSize": "13px", "opacity": 0.95}),
            ],
        ),
        dcc.Graph(id="graph_latency", style={"height": "420px"}),
        dcc.Graph(id="graph_load", style={"height": "360px"}),
        html.Div(
            style={"marginTop": "8px", "fontSize": "13px", "opacity": 0.9},
            children=[
                html.Div("Definitions:"),
                html.Ul([
                    html.Li("lambda_target is the commanded transaction submission rate."),
                    html.Li("submitted_tps is derived from delta sent_total over wall-clock time."),
                    html.Li("saturation_score is submitted_tps divided by lambda_target."),
                    html.Li("lat_p99 is observed confirmation latency, not a feedback-control variable in this layer."),
                ]),
            ],
        ),
        dcc.Interval(id="tick", interval=int(TS * 1000), n_intervals=0),
    ],
)


@app.callback(Output("sat_badge", "children"), Output("sat_badge", "style"), Input("tick", "n_intervals"))
def sat_badge_cb(_):
    snap = STATE.snapshot()
    style = {"background": "#eee", "color": "#333", "padding": "6px 10px", "borderRadius": "10px", "fontWeight": "600"}
    if not snap["t"] or not snap["last_ok"]:
        return "saturation: N/A", style
    sat = snap["sat"][-1]
    if isinstance(sat, float) and math.isnan(sat):
        return "saturation: NaN", style
    ok = sat >= SAT_BAD
    return f"saturation={sat:.2f}", {**style, "fontWeight": "700", "background": "#d7f5dd" if ok else "#ffe2e2", "color": "#163" if ok else "#611"}


@app.callback(Output("status_line", "children"), Input("tick", "n_intervals"))
def status_cb(_):
    snap = STATE.snapshot()
    if not snap["last_ok"]:
        return f"ERROR polling: {snap['last_err']}"
    if not snap["t"]:
        return "OK. Waiting for first samples."
    return (
        f"OK t={snap['t'][-1]:.1f}s "
        f"lambda={fnum(snap['u_cmd'][-1],1)} "
        f"submitted={fnum(snap['u_ach'][-1],1)} "
        f"inflight={fnum(snap['inflight'][-1],0)} "
        f"err/s={fnum(snap['err_s'][-1],1)} "
        f"lat_p99={fnum(snap['lat'][-1],3)}s"
    )


@app.callback(Output("graph_latency", "figure"), Input("tick", "n_intervals"), State("inp_yref", "value"), State("inp_ymax", "value"))
def latency_fig_cb(_, yref, ymax):
    snap = STATE.snapshot()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=snap["t"], y=snap["lat"], mode="lines", name="tx_latency_p99"))
    if yref is not None:
        fig.add_hline(y=float(yref), line_dash="dash", annotation_text="reference", annotation_position="top left")
    if ymax is not None:
        fig.add_hline(y=float(ymax), line_dash="dot", annotation_text="SLO", annotation_position="top left")
    fig.update_layout(title="Observed transaction latency p99", xaxis_title="time, s", yaxis_title="seconds", legend=dict(orientation="h"), margin=dict(l=40, r=20, t=55, b=40))
    return fig


@app.callback(Output("graph_load", "figure"), Input("tick", "n_intervals"))
def load_fig_cb(_):
    snap = STATE.snapshot()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=snap["t"], y=snap["u_cmd"], mode="lines", name="lambda_target"))
    fig.add_trace(go.Scatter(x=snap["t"], y=snap["u_ach"], mode="lines", name="submitted_tps"))
    fig.add_trace(go.Scatter(x=snap["t"], y=snap["sent_reported"], mode="lines", name="sent_per_sec reported"))
    fig.add_trace(go.Scatter(x=snap["t"], y=snap["err_s"], mode="lines", name="err/s"))
    fig.add_trace(go.Scatter(x=snap["t"], y=snap["inflight"], mode="lines", name="inflight", yaxis="y2"))
    fig.update_layout(title="Controlled-load throughput tracking", xaxis_title="time, s", yaxis_title="tx/s", yaxis2=dict(title="inflight", overlaying="y", side="right"), legend=dict(orientation="h"), margin=dict(l=40, r=40, t=55, b=40))
    return fig


@app.callback(Output("inp_lambda", "value"), Input("btn_apply", "n_clicks"), State("inp_lambda", "value"), prevent_initial_call=True)
def apply_lambda_cb(_, lam):
    if lam is None:
        return 20
    lam = float(lam)
    safe_post_json(LOADGEN_RATE, {RATE_KEY: lam}, timeout=1.0)
    STATE.current_cmd = lam
    return lam


def main():
    th = threading.Thread(target=poll_loop, daemon=True)
    th.start()
    app.run(host=os.environ.get("DASH_HOST", "0.0.0.0"), port=int(os.environ.get("DASH_PORT", "8050")), debug=False)


if __name__ == "__main__":
    main()
