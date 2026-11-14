# CQ Prerecorder

IC-7300とIC-7610のボイス送信（Voice TX）用にWAVを変換します。音量正規化やゲイン調整の工程はありません。

## 準備と起動

uvを用意し、FFmpegをPATHに追加します。プロジェクトのルートに `submitted_wav/` を作り、変換元のWAVを入れてから実行してください。

```powershell
uv run cq-prerecorder
```

## SDカード用WAVを作る

| 出力フォルダー | 機種 | 音声形式 | SDカード上の配置先 |
| --- | --- | --- | --- |
| `wav_IC7300/` | IC-7300 | 8 kHz・モノラル・16-bit PCM | `IC-7300/VoiceTx/` |
| `wav_IC7610/` | IC-7610 | 16 kHz・モノラル・16-bit PCM | `IC-7610/VoiceTx/` |

起動メニューで **SDカード用WAVを作る** を選ぶと、左に T1〜T8 の割り当て、右に音声候補が表示されます。

- `↑`／`↓` または `W`／`S` で候補を移動し、Enter で割り当てます。
- `←`／`→`、`A`／`D`、または `1`〜`8` で割り当て先を選び直せます。
- 1枠以上を割り当てて `G` を押すと、選んだ枠だけ生成します。`Q` で中止できます。

選んだ音声を `submitted_wav/` から直接変換し、`wav_IC7300/sdcard/` と `wav_IC7610/sdcard/` に枠番号に対応するWAVを生成します。例えば、T3を選ぶと `voicetx3.wav` を生成します。未選択の枠に既存のWAVがあれば、そのまま残ります。使う機種の `sdcard/` から必要なWAVを、表のSDカード上の配置先にコピーしてください。 [IC-7300取扱説明書](https://www.icomfrance.com/uploads/files/produit/not-IC-7300_ENG_FM_12-en.pdf) · [IC-7610詳細取扱説明書](https://www.northcom.se/downloadable/download/sample/sample_id/348/)

## 全音声を変換する

起動メニューで **全音声を変換する** を選ぶか、`uv run cq-prerecorder --convert-only` を実行すると、候補全体を元のファイル名で機種別フォルダー直下に書き出します。どちらのモードも出力先の同名ファイルを更新します。

WAV内の表示名はファイル名から取った半角16文字です。`ふなはし.wav` は無線機上で `funahashi` と表示する設定で、その他の非ASCII文字は `?` に置き換えます。
