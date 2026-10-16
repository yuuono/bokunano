"""既存結果を保持し、1M・1epochの4修正候補と3対照を別runで比較する。"""

# 直接実行時も共通runnerをimportできるようにする
from pathlib import Path
import sys

# リポジトリ直下を検索先に追加する
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# 学習・保存・全件評価は既存経路を使い、候補の設定を分離する
from scripts.model.run_boku_nano_looped_experiment import (  # noqa: E402
    REVISION_COMPARISON, main,
)

# 指定なしでは設定生成だけを行い、学習は--runで明示する
if __name__ == "__main__":
    main(default_variants=REVISION_COMPARISON, default_epochs=1,
         allowed_variants=REVISION_COMPARISON, description=__doc__)
