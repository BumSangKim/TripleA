# chart_generator.py
# Matplotlib 기반 경제지표 차트 생성 (헤드리스 서버 환경 지원)
import matplotlib
matplotlib.use("Agg")  # 헤드리스 서버 환경 필수
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import logging

from database import get_latest
from preprocessor import clean_series, detect_changepoint

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
# 한글 폰트 설정
# ────────────────────────────────────────────────
def set_korean_font():
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/nanum/NanumGothic.ttf",
        "NanumGothic",
        "AppleGothic",    # macOS
        "Malgun Gothic",  # Windows
    ]
    for font in candidates:
        try:
            prop = fm.FontProperties(fname=font) if font.endswith(".ttf") else fm.FontProperties(family=font)
            found = fm.findfont(prop, fallback_to_default=False)
            if found and "DejaVu" not in found:
                plt.rcParams["font.family"] = prop.get_name()
                return
        except Exception:
            continue
    plt.rcParams["font.family"] = "sans-serif"

set_korean_font()
plt.rcParams["axes.unicode_minus"] = False


def create_multi_chart(
    indicators: list,
    db_path: str = "economic_data.db",
) -> io.BytesIO:
    """
    여러 지표를 2열 격자 차트로 생성
    indicators: [("KOSPI", "코스피"), ("USD_KRW", "원/달러 환율"), ...]
    반환: PNG BytesIO (텔레그램 직접 전송 가능)
    """
    import pandas as pd

    n = len(indicators)
    cols = 2
    rows = (n + 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(12, rows * 3))
    axes = axes.flatten() if n > 1 else [axes]

    for i, (key, label) in enumerate(indicators):
        df = get_latest(key, n=60, db_path=db_path)
        if df.empty:
            axes[i].text(0.5, 0.5, "데이터 없음", ha="center", va="center", fontsize=12)
            axes[i].set_title(label)
            continue

        df = clean_series(df)
        try:
            x = pd.to_datetime(df["date"])
        except Exception:
            x = range(len(df))
        y = df["value"].astype(float)

        axes[i].plot(x, y, color="#1E88E5", linewidth=1.5)
        axes[i].fill_between(x, y, alpha=0.1, color="#1E88E5")
        axes[i].set_title(label, fontsize=11, fontweight="bold")
        axes[i].grid(True, alpha=0.3, linestyle="--")
        axes[i].tick_params(axis="x", rotation=30, labelsize=7)

        # 변화점 표시
        changepoints = detect_changepoint(df)
        for cp in changepoints:
            if cp < len(x):
                axes[i].axvline(x=list(x)[cp], color="red", linestyle="--", alpha=0.5, linewidth=1)

    # 빈 서브플롯 숨기기
    for j in range(len(indicators), len(axes)):
        axes[j].set_visible(False)

    fig.suptitle("주요 경제지표 추이", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def create_capex_chart(db_path: str = "economic_data.db") -> io.BytesIO:
    """
    Hyperscaler CapEx 분기 추이 Bar Chart (MSFT/GOOGL/META/AMZN)
    DB에서 최근 5분기 데이터 조회하여 그룹 막대그래프 생성
    """
    import sqlite3
    import numpy as np
    import pandas as pd

    TICKERS = {
        "CAPEX_MSFT":  ("Microsoft",  "#00BCF2"),
        "CAPEX_GOOGL": ("Alphabet",   "#34A853"),
        "CAPEX_META":  ("Meta",       "#1877F2"),
        "CAPEX_AMZN":  ("Amazon",     "#FF9900"),
    }

    # 각 종목별 데이터 수집
    conn = sqlite3.connect(db_path)
    all_quarters = set()
    series = {}
    for key, (name, color) in TICKERS.items():
        rows = conn.execute(
            "SELECT date, value FROM indicators WHERE indicator=? ORDER BY date DESC LIMIT 5",
            (key,),
        ).fetchall()
        if rows:
            data = {r[0]: r[1] for r in rows}
            series[name] = {"data": data, "color": color}
            all_quarters.update(data.keys())
    conn.close()

    if not series:
        # 데이터 없으면 빈 차트
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, "CapEx 데이터 없음", ha="center", va="center", fontsize=14)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf

    quarters = sorted(all_quarters)  # 날짜 오름차순
    n_q = len(quarters)
    n_companies = len(series)
    x = np.arange(n_q)
    width = 0.18

    fig, ax = plt.subplots(figsize=(12, 5))
    for i, (name, info) in enumerate(series.items()):
        vals = [info["data"].get(q, 0) for q in quarters]
        offset = (i - n_companies / 2 + 0.5) * width
        bars = ax.bar(x + offset, vals, width, label=name, color=info["color"], alpha=0.85)
        # 값 레이블
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.3,
                    f"${val:.1f}B",
                    ha="center", va="bottom", fontsize=7, fontweight="bold",
                )

    # 분기 라벨 (YYYY-MM-DD → YYYYQN 형식)
    def to_quarter(d):
        try:
            m = int(d[5:7])
            y = d[:4]
            q = (m - 1) // 3 + 1
            return f"{y}Q{q}"
        except Exception:
            return d

    ax.set_xticks(x)
    ax.set_xticklabels([to_quarter(q) for q in quarters], fontsize=9)
    ax.set_ylabel("CapEx (십억달러, B USD)", fontsize=10)
    ax.set_title("Hyperscaler AI CapEx 분기 추이 (Deep Research S1)", fontsize=13, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf
