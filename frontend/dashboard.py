# dashboard.py
# Streamlit 기반 퀀트 모니터링 대시보드
# 실행: PYTHONPATH=. streamlit run frontend/dashboard.py
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from storage.database import DB_PATH as DEFAULT_DB_PATH

try:
    import streamlit as st
except ImportError:
    print("streamlit이 설치되지 않았습니다. 'pip install streamlit' 을 실행하세요.")
    sys.exit(1)

DB_PATH = Path(DEFAULT_DB_PATH)

st.set_page_config(
    page_title="TripleA 퀀트 대시보드",
    page_icon="📈",
    layout="wide",
)

st.title("📈 TripleA 퀀트 모니터링 대시보드")


# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_indicators(limit: int = 30) -> pd.DataFrame:
    """최근 수집된 주요 지표 로드."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT i.indicator, i.date, i.value, i.unit, i.source, i.is_stale
        FROM indicators i
        INNER JOIN (
            SELECT indicator, MAX(date) AS max_date
            FROM indicators
            GROUP BY indicator
        ) latest ON i.indicator = latest.indicator AND i.date = latest.max_date
        ORDER BY i.indicator
        """,
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_features() -> pd.DataFrame:
    """최근 기술적 지표 피처 로드 (각 지표별 최신 1건)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            """
            SELECT f.*
            FROM features f
            INNER JOIN (
                SELECT indicator, MAX(computed_at) AS max_at
                FROM features
                GROUP BY indicator
            ) latest ON f.indicator = latest.indicator AND f.computed_at = latest.max_at
            ORDER BY f.indicator
            """,
            conn,
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_signals(n: int = 50) -> pd.DataFrame:
    """최근 매매 신호 로드."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            f"""
            SELECT id, indicator, signal_type, strategy, confidence, price, detail, created_at
            FROM signals
            ORDER BY created_at DESC
            LIMIT {n}
            """,
            conn,
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_price_history(indicator: str, limit: int = 120) -> pd.DataFrame:
    """특정 지표의 가격 이력 로드."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT date, value FROM indicators
        WHERE indicator = ? AND is_stale = 0
        ORDER BY date DESC LIMIT ?
        """,
        conn,
        params=(indicator, limit),
    )
    conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df


@st.cache_data(ttl=300)
def load_valuation_results() -> pd.DataFrame:
    """최신 밸류에이션 결과 로드."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            """
            SELECT v.*
            FROM valuation_results v
            INNER JOIN (
                SELECT ticker, MAX(date) AS max_date
                FROM valuation_results
                GROUP BY ticker
            ) latest ON v.ticker = latest.ticker AND v.date = latest.max_date
            ORDER BY v.overvaluation_score DESC
            """,
            conn,
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_bottleneck_history(n: int = 52) -> pd.DataFrame:
    """병목지수 이력 로드 (최근 n 관측치)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            f"""
            SELECT date, bottleneck_index, z_pmi_sdt, z_wti, z_us10y, z_inflation
            FROM bottleneck_scores
            ORDER BY date DESC LIMIT {n}
            """,
            conn,
        )
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


# ── 탭 구성 ───────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 핵심 지표", "🔬 기술적 지표", "📡 매매 신호", "📉 차트", "💹 밸류에이션"])

# ── Tab 1: 핵심 지표 현황 ──────────────────────────────────────────────────────
with tab1:
    st.subheader("핵심 경제 지표 스냅샷")
    df_ind = load_indicators()
    if df_ind.empty:
        st.info("수집된 지표가 없습니다. `python -m backend.main` 를 먼저 실행하세요.")
    else:
        KEY_INDS = [
            "KOSPI", "KOSDAQ", "USD_KRW", "GOLD", "WTI", "DUBAI_OIL",
            "CPI", "US_CPI", "US10Y", "US_FEDFUNDS",
            "SMH", "SPY", "RS_SMH_SPY",
        ]
        highlight = df_ind[df_ind["indicator"].isin(KEY_INDS)].copy()
        others    = df_ind[~df_ind["indicator"].isin(KEY_INDS)]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**주요 지표**")
            if not highlight.empty:
                highlight["값"] = highlight["value"].map(lambda v: f"{v:,.4f}")
                highlight["날짜"] = highlight["date"]
                highlight["비고"] = highlight["is_stale"].map(lambda s: "⚠️ STALE" if s else "✅")
                st.dataframe(
                    highlight[["indicator", "값", "unit", "날짜", "비고"]].rename(columns={"indicator": "지표", "unit": "단위"}),
                    use_container_width=True,
                    hide_index=True,
                )
        with col2:
            st.markdown("**전체 지표 수집 현황**")
            stale_cnt  = int(df_ind["is_stale"].sum())
            active_cnt = len(df_ind) - stale_cnt
            st.metric("수집 완료", active_cnt)
            st.metric("STALE (전일 대체)", stale_cnt)

        with st.expander("전체 지표 보기"):
            st.dataframe(df_ind, use_container_width=True, hide_index=True)

# ── Tab 2: 기술적 지표 ────────────────────────────────────────────────────────
with tab2:
    st.subheader("기술적 지표 피처 (RSI · MA · MACD · 볼린저 밴드)")
    df_feat = load_features()
    if df_feat.empty:
        st.info("기술적 지표 피처가 없습니다. `python -m backend.main` 를 실행하면 자동으로 계산됩니다.")
    else:
        SIGNAL_COLS = ["indicator", "rsi14", "rsi_signal", "sma5", "sma20", "ma_signal",
                       "macd", "macd_hist", "macd_bias", "bb_upper", "bb_lower", "bb_bandwidth"]
        avail = [c for c in SIGNAL_COLS if c in df_feat.columns]
        display = df_feat[avail].copy()

        def _rsi_color(val):
            if isinstance(val, str):
                if val == "OVERBOUGHT": return "background-color: #ffcccc"
                if val == "OVERSOLD":   return "background-color: #ccffcc"
            return ""

        st.dataframe(
            display.style.applymap(_rsi_color, subset=[c for c in ["rsi_signal", "ma_signal", "macd_bias"] if c in display.columns]),
            use_container_width=True,
            hide_index=True,
        )

# ── Tab 3: 매매 신호 ─────────────────────────────────────────────────────────
with tab3:
    st.subheader("최근 매매 신호 (자동 생성)")
    df_sig = load_signals(50)
    if df_sig.empty:
        st.info("신호 없음. `python -m backend.main` 실행 후 데이터 충분 시 자동으로 신호가 생성됩니다.")
    else:
        BUY_STYLE  = "background-color: #d4edda; color: #155724"
        SELL_STYLE = "background-color: #f8d7da; color: #721c24"

        def _sig_color(val):
            if val == "BUY":  return BUY_STYLE
            if val == "SELL": return SELL_STYLE
            return ""

        df_sig["confidence_%"] = (df_sig["confidence"] * 100).round(1)
        st.dataframe(
            df_sig[["created_at", "indicator", "signal_type", "strategy", "confidence_%", "price", "detail"]].rename(
                columns={"created_at": "시간", "indicator": "지표", "signal_type": "신호", "strategy": "전략",
                         "confidence_%": "신뢰도(%)", "price": "가격", "detail": "상세"}
            ).style.applymap(_sig_color, subset=["신호"]),
            use_container_width=True,
            hide_index=True,
        )

        buy_cnt  = int((df_sig["signal_type"] == "BUY").sum())
        sell_cnt = int((df_sig["signal_type"] == "SELL").sum())
        c1, c2 = st.columns(2)
        c1.metric("최근 BUY 신호", buy_cnt)
        c2.metric("최근 SELL 신호", sell_cnt)

# ── Tab 4: 가격 차트 ──────────────────────────────────────────────────────────
with tab4:
    st.subheader("지표 가격 이력 차트")
    CHART_OPTIONS = ["KOSPI", "KOSDAQ", "USD_KRW", "GOLD", "WTI", "US500", "SMH", "SPY", "US10Y"]
    selected = st.selectbox("지표 선택", CHART_OPTIONS, index=0)
    df_price = load_price_history(selected, 200)
    if df_price.empty:
        st.info(f"{selected} 데이터가 없습니다.")
    else:
        st.line_chart(df_price.set_index("date")["value"], use_container_width=True)
        st.caption(f"최근 {len(df_price)}일 데이터")

# ── Tab 5: 밸류에이션 스크리닝 ────────────────────────────────────────────────
with tab5:
    st.subheader("💹 밸류에이션 스크리닝")

    # 병목지수 현황
    df_bn = load_bottleneck_history(52)
    if not df_bn.empty:
        latest_bn = df_bn["bottleneck_index"].iloc[-1]
        bn_delta = (
            latest_bn - df_bn["bottleneck_index"].iloc[-2]
            if len(df_bn) > 1
            else None
        )

        def _bn_label(val) -> str:
            if val >= 2.0: return "🔴 심각 병목"
            if val >= 1.0: return "🟠 병목 주의"
            if val >= 0.0: return "🟡 경미한 병목"
            return "🟢 공급망 완화"

        col_bn1, col_bn2 = st.columns([1, 3])
        with col_bn1:
            st.metric("현재 병목지수", f"{latest_bn:.2f}σ", delta=f"{bn_delta:+.2f}σ" if bn_delta is not None else None)
            st.caption(_bn_label(latest_bn))
        with col_bn2:
            st.line_chart(df_bn.set_index("date")["bottleneck_index"], use_container_width=True)
            st.caption("병목지수 추이 (가중 Z-score 복합지수)")
    else:
        st.info("병목지수 데이터 없음. 파이프라인 실행 후 확인하세요.")

    st.divider()

    # 밸류에이션 결과 테이블
    st.subheader("종목별 적정 멀티플 vs 현재 멀티플")
    df_val = load_valuation_results()

    if df_val.empty:
        st.info(
            "밸류에이션 데이터가 없습니다. "
            "`python -m backend.main --force` 또는 `backend.valuation_pipeline`를 실행하세요."
        )
    else:
        # 신호 배지 색상
        SIGNAL_COLORS = {
            "명확한 고평가": "#f8d7da",
            "고평가 경계":   "#fff3cd",
            "적정":          "#d4edda",
            "저평가 경계":   "#cce5ff",
            "명확한 저평가": "#b8daff",
        }

        def _signal_style(val):
            color = SIGNAL_COLORS.get(val, "")
            return f"background-color: {color}" if color else ""

        def _mp_style(val):
            if not isinstance(val, float):
                return ""
            if val > 0.10:  return "color: #c0392b"  # 빨강 (고평가)
            if val < -0.10: return "color: #1a7a4a"  # 초록 (저평가)
            return ""

        display_cols = {
            "ticker": "티커",
            "sector": "섹터",
            "current_ev_ebitda": "현재 EV/EBITDA",
            "fair_ev_ebitda": "적정 EV/EBITDA",
            "mispricing_ev_ebitda": "EV 괴리율",
            "current_per": "현재 P/E",
            "fair_per": "적정 P/E",
            "overvaluation_score": "종합 스코어",
            "valuation_signal": "판단",
            "model_type": "모델",
        }
        avail_cols = [c for c in display_cols if c in df_val.columns]
        df_display = df_val[avail_cols].rename(columns=display_cols).copy()

        # 괴리율을 % 문자열로 표시
        if "EV 괴리율" in df_display.columns:
            df_display["EV 괴리율"] = df_display["EV 괴리율"].apply(
                lambda v: f"{v * 100:+.1f}%" if pd.notna(v) else "N/A"
            )

        # EV/EBITDA 소수점 1자리
        for col in ["현재 EV/EBITDA", "적정 EV/EBITDA", "현재 P/E", "적정 P/E"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(
                    lambda v: f"{v:.1f}x" if pd.notna(v) else "N/A"
                )

        if "종합 스코어" in df_display.columns:
            df_display["종합 스코어"] = df_display["종합 스코어"].apply(
                lambda v: f"{v:+.3f}" if pd.notna(v) else "N/A"
            )

        styled = df_display.style.applymap(
            _signal_style, subset=["판단"] if "판단" in df_display.columns else []
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # 요약 지표
        if "판단" in df_val.columns:
            ov_cnt = int((df_val["overvaluation_score"] > 0.10).sum())
            uv_cnt = int((df_val["overvaluation_score"] < -0.10).sum())
            ok_cnt = len(df_val) - ov_cnt - uv_cnt
            c1, c2, c3 = st.columns(3)
            c1.metric("🔴 고평가", ov_cnt)
            c2.metric("⚪ 적정", ok_cnt)
            c3.metric("🟢 저평가", uv_cnt)

        # 병목지수 분해 차트
        if not df_bn.empty:
            with st.expander("병목지수 구성 요소 보기"):
                component_cols = [c for c in ["z_pmi_sdt", "z_wti", "z_us10y", "z_inflation"] if c in df_bn.columns]
                if component_cols:
                    st.line_chart(df_bn.set_index("date")[component_cols], use_container_width=True)
                    st.caption("GSCPI/PMI(40%) · WTI(30%) · US10Y(20%) · CPI(10%) Z-스코어")

# ── 하단 정보 ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("TripleA 퀀트 모니터링 시스템 | DB: " + str(DB_PATH))
if st.button("새로고침"):
    st.cache_data.clear()
    st.rerun()
