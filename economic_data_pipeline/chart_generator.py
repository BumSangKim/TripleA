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
