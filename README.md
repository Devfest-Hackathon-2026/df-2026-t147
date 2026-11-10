# DevFest Hackathon 2026 提出用リポジトリ

  DevFest Hackathon 2026 のチームの **最終提出用** リポジトリです。提出期限までに、作品のコードと資料をこのリポジトリに置いてください。

  このリポジトリは **公開（public）** です。開催中も、運営・審査員・ほかの参加者が見られます。

  ## はじめに

  1. GitHub から届いた招待を受け入れてください（招待の期限は 7 日です）
  2. このリポジトリを clone して、提出物を置いてください

  招待の期限が切れたときや、メンバーが変わったときは、運営に連絡してください。

  ## 開発用のリポジトリは別に作ることをおすすめします

  このリポジトリでは **GitHub Actions と GitHub Pages が使えません**。CI やデプロイ、Pages での公開をしたいときは、チームで開発用のリポジトリを別に作ってください。

  - 開発用のリポジトリは、チームのメンバーのアカウントや、チームで作った Organization に作ってください
  - 開発はそちらで進めて、提出期限までに最終版のコードと資料をこのリポジトリに push してください
  - 審査はこのリポジトリの内容で行います。開発用のリポジトリにしかないものは、審査の対象になりません
  - デプロイした作品の URL があれば、この README に書いてください

  ## 秘密情報をコミットしない

  API キー・パスワード・サービスアカウントの鍵などは、**絶対にコミットしないでください**。公開リポジトリなので、push
  した時点で誰でも見られます。開発用のリポジトリから持ってくるときも、履歴ごと push すると、過去のコミットに含まれる秘密情報も公開されます。

  - 秘密情報は `.env` や `.dev.vars` などに書き、コミットしない（`.gitignore` に入れてあります）
  - 誤って push したら、すぐにキー（鍵）を無効にして作り直し、運営に連絡してください。履歴から消すだけでは不十分です
  - GitHub の push protection が、よく知られた形式のキーの push を止めることがあります。止められたら、そのキーをコミットから外してください

  ## 提出

  提出の方法と締切は、運営からの案内に従ってください。提出期限を過ぎると、このリポジトリは読み取り専用になり、push できなくなります。

  ## ライセンス

  [MIT License](LICENSE) です。ほかのライセンスにしたいときは、LICENSE を書き換えてください。


## 「ねぇ、できた」とは
子どもが歯みがきのあとに「できたよ」と報告し、質問に3つ答えると、相棒のハミーが育つアプリです。
保護者は、記録から数えた「ほめどころ」を見て承認し、承認が3日たまるごとに、歯にいいアイテムが1つ届きます。
日数や連続の数え方はルールで決め、言葉づくり（質問や声かけ）だけを Gemini が担当します。失敗したときは固定文に切り替わります。

## 本番URL
https://habit-rpg-875385081988.asia-northeast1.run.app

## 構成
- Cloud Run: API とフロントを1つのコンテナで配信
- Firestore: データ保存
- Vertex AI（Gemini）: 質問・声かけ・傾向の一文の生成

## ローカル起動
```bash
# backend
cd backend && python -m venv ../.venv && . ../.venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q                       # テスト
DEMO_MODE=1 uvicorn app.main:app --reload # :8000（DEMO_MODE=1 はローカル専用）
# frontend（別ターミナル）
cd frontend && npm install && npm run dev # :5173（/api は 8000 へ中継）
```
デモデータ: `python backend/scripts/seed_demo.py http://localhost:8000`（出力された localStorage のコマンドをブラウザで実行）。
`?now=2026-11-10T10:00:00%2B09:00` を URL に付けると日付を擬似的に進められる（DEMO_MODE=1 のときのみ有効）。

## 画像素材の差し替え（Figmaデザインの反映）
`frontend/public/art/<名前>.png` を置くと、仮のSVGから自動で差し替わる（コード変更なし）。
- 相棒: `buddy_egg` `buddy_baby` `buddy_minarai` `buddy_adult` `buddy_sad` `buddy_start`、敵: `demon`
- アイテム: `item_calcium` `item_phosphorus` `item_vitd` `item_vitc`
- 部品: `sun_window` `mat` `nav_brush` `nav_grow` `nav_items`
フォント（Dela Gothic One / M PLUS Rounded 1c、いずれも SIL OFL）は npm の @fontsource で同梱。

## デモモードはローカル専用
`DEMO_MODE=1` を付けて起動したときだけ、日付を操作するパネルと、デモ用データの投入が使えます。
Cloud Run には設定しません。設定しない本番では、日付を偽装するヘッダは無視されます。

## ゲームルール
- 成長: 通算の歯みがき日数（1日〜あかちゃん、5日〜みならい、15日〜りっぱな大人。途切れても戻らない）
- アイテム: 連続3日ごとに1つ。カルシウム→リン→ビタミンD→ビタミンCの順（記録から算出）
- さぼり演出: 丸3日やらなかったときだけ（責めない文言。1回磨けば戻る）

## 環境変数
使う変数の名前（値は書きません）: STORAGE / DATA_FILE / GEMINI_ENABLED / GEMINI_MODEL / GEMINI_TIMEOUT_MS / QUESTION_TIMEOUT_MS / GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION / STATIC_DIR / DEMO_MODE

| 変数 | 既定 | 意味 |
|---|---|---|
| STORAGE | memory | `firestore` で Firestore。memory は再起動で消える（DATA_FILE を指定するとJSON保存） |
| GEMINI_ENABLED | 0 | `1` で Vertex AI(Gemini) を使用 |
| GEMINI_MODEL | gemini-3.8-flash | |
| GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION | – / global | |
| DEMO_MODE | 0 | 本番では設定しない（日付偽装ヘッダを許可してしまう） |
| QUESTION_TIMEOUT_MS | 5000 | 子への質問の生成だけの待ち時間 |

## Cloud Run へのデプロイ（実行基盤の必須要件を満たす）
```bash
PROJECT=<your-project>; REGION=asia-northeast1
gcloud config set project $PROJECT
gcloud services enable run.googleapis.com firestore.googleapis.com aiplatform.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud firestore databases create --location=$REGION          # 初回のみ（ネイティブモード）

gcloud run deploy habit-rpg --source . --region $REGION --allow-unauthenticated \
  --set-env-vars STORAGE=firestore,GEMINI_ENABLED=1,GOOGLE_CLOUD_LOCATION=global,GOOGLE_CLOUD_PROJECT=$PROJECT

# サービスアカウントに権限（Cloud Run の実行SA。既定はCompute Engine既定SA）
SA=$(gcloud run services describe habit-rpg --region $REGION --format='value(spec.template.spec.serviceAccountName)')
for R in roles/datastore.user roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$SA --role=$R; done
```
- 家族コードがURLの代わりの認証なので、提出物のリポジトリ/動画に `fid` を載せない。
- 認証なし公開のため、Cloud Run の `--max-instances` を小さく（例: 3）して課金暴走を防ぐこと。
- 任意: Firebase Hosting で静的配信し `/api/**` を Cloud Run に rewrite する構成も可（`firebase.json` の rewrites に `{"source":"/api/**","run":{"serviceId":"habit-rpg","region":"asia-northeast1"}}`）。

## 未検証（正直な申告）
- Gemini 呼び出し（VertexLLM）と Firestore アダプタは、認証情報のあるGCP環境でのみ動作確認可能。ローカルでは固定文フォールバックとMemoryStoreで検証済み（pytest 39件 + Playwright E2E）。
- 禁止ワード・文字数チェックは最低限。審査前に実出力を数十件目視確認すること。

## ハッカソン提出時の注意
- GitHub は主催者が作るリポジトリへ最終版のみpush。`.env`・鍵・`fid` を含めない。
- デモ動画のデータは「デモ用データ」バッジ付き（画面右上）。
