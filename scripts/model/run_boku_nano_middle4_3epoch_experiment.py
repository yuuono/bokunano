#!/usr/bin/env python3
"""中間層4回反復を3epoch学習し、反復部の残差倍率1.0と0.25を比較する。"""

from run_boku_nano_looped_experiment import MIDDLE4_3EPOCH_COMPARISON, main


if __name__ == "__main__":
    main(
        default_variants=MIDDLE4_3EPOCH_COMPARISON,
        default_epochs=3,
        allowed_variants=MIDDLE4_3EPOCH_COMPARISON,
        description=__doc__,
    )
