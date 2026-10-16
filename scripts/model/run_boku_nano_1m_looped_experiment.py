"""既存1Mの3層を維持し、1epochで通常版・2周・3周を比較する。"""

# 直接実行でもリポジトリ内の共通runnerを読み込めるようにする
from pathlib import Path
import sys

# リポジトリ直下をmodule検索先へ追加する
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# モデル生成・検証・学習・評価には既存の共通処理を使う
from scripts.model.run_boku_nano_looped_experiment import (  # noqa: E402
    ONE_M_COMPARISON, main,
)

# import時には学習せず、CLIとして呼ばれた場合だけ設定を生成する
if __name__ == "__main__":
    # 全候補を1,016,704 parametersへ固定し、6周は任意の追加比較にする
    main(default_variants=ONE_M_COMPARISON, default_epochs=1,
         allowed_variants=[*ONE_M_COMPARISON, "u3_r6"], description=__doc__)
