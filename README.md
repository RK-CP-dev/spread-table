# 取引所スプレッド率テーブル（平日14時 自動更新）

CoinPostの「取引所ランキング記事」に掲載する、BTC/JPYスプレッド率テーブルの自動更新システムです。

取引所4社（GMOコイン・bitFlyer・Coincheck・bitbank）の公開APIから平日（月〜金）14時に自動でスプレッド率を集計し、WordPress記事内の表を最新に保ちます。

> **SBI VCトレードについて**：当初5社の予定でしたが、SBI VCトレードは認証不要のパブリックticker APIの存在が確認できなかったため（依頼書記載の `api.sbivc.co.jp` はドメイン自体が存在せず）、4社構成としています。今後APIが確認できた場合は `scripts/collect_spread.py` の `EXCHANGES` にエントリを追加するだけで対応できます。

## システム全体図

```
[GitHub Actions]                       [WordPress]
平日スクリプト実行                       「追加文章」機能に表示用HTMLを登録
（月〜金 14:03 JST）                    → ショートコード [addtexts addid=XXXX] が発行される
4社のAPIをサーバー側で取得       →      → 記事にショートコードを挿入すると表が表示される
スプレッド率を計算                            ↑
     ↓                                       │
spread.json を生成・commit                    │
     ↓                                       │
GitHub Pages で配信 ──────────────────────────┘
（HTMLの中のJSが spread.json をfetchして描画。
  Pagesは Access-Control-Allow-Origin: * を自動付与するためCORS問題なし）
```

### 各ファイルの役割

| ファイル | 役割 |
|---|---|
| `scripts/collect_spread.py` | 4社のAPIからask/bidを取得しスプレッド率を計算するスクリプト |
| `.github/workflows/update-spread.yml` | 上記スクリプトを平日（月〜金）14:03(JST)に自動実行するワークフロー |
| `.github/workflows/keepalive.yml` | 60日無活動によるワークフロー自動停止への保険（通常は何もしない） |
| `docs/spread.json` | 集計結果データ（GitHub Pagesで配信される） |
| `wordpress/addtexts-block.html` | WPの「追加文章」に貼り付ける表示用HTML |

### セキュリティについて

- **APIキー等の秘匿情報は一切使用していません**。4社のAPIはすべて認証不要のパブリックAPIです。
- ワークフローのcommitはGitHubが自動発行する`GITHUB_TOKEN`を使用します（コードに書かれていません）。
- 第三者製のGitHub Actionsは公式（actions/checkout, actions/setup-python）以外使用せず、タグ差し替え攻撃を防ぐため**コミットSHAに固定**しています。
- ワークフローの権限は`contents: write`（このリポジトリへのcommit）のみに最小化しています。
- 表示側HTMLはJSON由来の文字列をすべてHTMLエスケープするため、万一データが改ざんされても記事上でスクリプトは実行されません。

### 運用コストについて

- **すべて無料枠内で動作します（¥0）**。パブリックリポジトリのGitHub ActionsとGitHub Pagesは無料です。
- サーバー・データベース等は不要です。

---

## 初回セットアップ手順

### 1. リポジトリの作成とpush

このファイル一式を **パブリックリポジトリ** としてGitHubにpushします。

> パブリックにする理由：GitHub Pagesが無料プランで使えるのはパブリックリポジトリのみのためです。リポジトリ内に秘匿情報は一切含まれないため、公開しても問題ありません。

### 2. リポジトリのセキュリティ設定（推奨・手作業）

リポジトリ作成直後に、GitHub画面で以下を設定してください。

1. **mainブランチの保護**
   - Settings → Branches → **Add branch ruleset**（または Add rule）
   - 対象ブランチ: `main`
   - 「Block force pushes」（force push禁止）を有効化
   - 「Restrict deletions」（ブランチ削除禁止）を有効化
   - ※「Require a pull request before merging」は**有効にしないでください**（ワークフローの自動commitが直接pushのため）
2. **不要機能の無効化**（スパム・フィッシングリンク設置の防止）
   - Settings → General → Features で **Issues・Wiki・Discussions・Projects のチェックを外す**
3. **書き込み権限の最小化**
   - Settings → Collaborators and teams で、書き込み権限（Write以上）を必要最小限のメンバーに限定

### 3. GitHub Pages の有効化

1. リポジトリの **Settings → Pages** を開く
2. 「Build and deployment」の Source を **Deploy from a branch** にする
3. Branch を **main**、フォルダを **`/docs`** にして Save

数分後、`https://rk-cp-dev.github.io/spread-table/spread.json` が配信されます。

### 4. 手動実行で動作確認

1. リポジトリの **Actions** タブ → 「Update spread data」を選択
2. **Run workflow** ボタンで手動実行
3. 実行が緑（成功）になることを確認
4. ブラウザで `https://rk-cp-dev.github.io/spread-table/spread.json` を開き、JSONが表示されることを確認
   （Pagesへの反映には数分かかることがあります）

### 5. 表示用HTMLのデータURL確認

`wordpress/addtexts-block.html` 内のデータURLは、本リポジトリのPages URLに**設定済み**です。

```javascript
var DATA_URL = "https://rk-cp-dev.github.io/spread-table/spread.json";
```

> リポジトリを別の組織・別名に移管した場合は、この1行を新しいPages URL（`https://<新オーナー名>.github.io/<新リポジトリ名>/spread.json`）に書き換え、WPの追加文章も更新してください。

### 6.【WP側の手作業】追加文章への登録

1. WP管理画面の **「追加文章」** を開く
2. `wordpress/addtexts-block.html` の中身を **すべてコピーして貼り付け**、保存
3. 自動発行されるショートコード（例：`[addtexts addid=721727]`）を控える

> **初回は必ず実機確認してください**：追加文章内の `<script>` タグがWP側のセキュリティプラグイン等で除去されていないか、実際の記事プレビューで表が表示されることを確認します。

### 7.【WP側の手作業】記事への挿入

取引所ランキング記事の掲載したい位置に、控えたショートコードを挿入して記事を更新します。

---

## 日々の運用

**基本は放置でOKです。** 平日（月〜金）14:03(JST)に自動更新されます。

月1回程度、以下を目視確認してください：

- ブラウザで `https://rk-cp-dev.github.io/spread-table/spread.json` を開き、`updated` の日付が直近の平日になっているか

---

## トラブルシューティング

### 表が「読み込み中…」のまま／「データを取得できませんでした」と表示される

以下の順で確認してください。

1. **Pages URLがブラウザで開けるか**
   `https://rk-cp-dev.github.io/spread-table/spread.json` を直接開く。
   - 開けない（404）→ Settings → Pages の設定を確認（手順3参照）
   - 開ける → 次へ

2. **Actionsの実行ログを確認**
   リポジトリの **Actions** タブ → 「Update spread data」の最新の実行を開く。
   - 赤（失敗）→ ログのエラーメッセージを確認。`WARNING`で特定の取引所名が出ていればその社のAPI障害または仕様変更
   - 実行自体がない → ワークフローが停止していないか確認（下記「60日停止」参照）

3. **各社API仕様変更の可能性**
   ログに特定の取引所の`fetch failed`が続く場合、その社のAPI仕様（URLやレスポンス形式）が変わった可能性があります。`scripts/collect_spread.py` の該当社のURL・パーサーを修正してください。1社の失敗では表全体は壊れず、取得できた社のみ表示されます。

### `updated` が古いまま更新されていない

- **Actions** タブでワークフローが実行されているか確認
- 60日以上活動がないとGitHubがスケジュール実行を自動停止します。Actionsタブに停止の通知バナーが出ていれば **Enable workflow** で再有効化してください（keepalive.ymlはこの停止を防ぐための保険です）

---

## 注意事項

- **ワークフロー失敗時はリポジトリ作成者にGitHubからメール通知が届きます**。通知が来たらActionsのログを確認してください。
- 追加文章内の `<script>` がWP側のセキュリティプラグイン等で除去されていないか、**初回に必ず実機確認**してください。
- bitbankのAPIは板（取引所）の値のため、表内の名称は「bitbank（取引所）」と表記し販売所レートと区別しています。

## 集計仕様

- スプレッド率(%) = (購入価格 − 売却価格) ÷ 購入価格 × 100
- 瞬間値のブレを均すため、1回の実行で3サンプル（2秒間隔）取得して平均
- **表に表示するスプレッド率は直近10営業日の平均**。spread.json内の`history`に直近10営業日分（日付・ask・bid・スプレッド率）を保持し、毎回のスプレッド率はその平均値（単一ファイル上書き方式のまま。別ファイル・外部DBは使わない）
  - 蓄積が10営業日に満たない間は、取得できた日数分の平均（`days`フィールドで日数を確認可能）
  - 当日取得に失敗した社は保持済み履歴のみで表示を継続（履歴も無い社は表から除外）
- 購入・売却価格（ask/bid）の表示は最新集計日の値
- サンプル数・間隔・平均日数は `scripts/collect_spread.py` 冒頭の定数で調整可能
- 評価記号のしきい値（◎：≤0.1%、△：≤0.6%、✕：それ超）は `wordpress/addtexts-block.html` 内の `ratingSymbol` 関数の定数で調整可能
