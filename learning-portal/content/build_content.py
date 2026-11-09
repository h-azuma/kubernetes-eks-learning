"""既存の設計書・ラボを読み取り、ポータル用教材を再生成する。"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = "docs/kubernetes-eks-hands-on-design.md"
LABS = [
    "labs/00-repository-foundation/README.md",
    "labs/01-compose-basics/README.md",
    "labs/02-kubernetes-basics/README.md",
]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def heading_body(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise ValueError(f"見出しがありません: {heading}")
    return match.group(1)


def lab_questions(text):
    return re.findall(r"^\d+\. (.+)$", heading_body(text, "設計課題（実装前に考える）"), re.M)


def memo_labels(text):
    rows = re.findall(r"^\| ([^|]+) \|[^\n]*$", heading_body(text, "学習メモ"), re.M)
    return [label.strip() for label in rows if label.strip() not in {"項目", "---"}]


def command_from(text, prefix):
    for block in re.findall(r"```[^\n]*\n(.*?)```", text, re.S):
        for line in block.splitlines():
            if line.startswith(prefix):
                return line
    raise ValueError(f"ラボ内にコマンドがありません: {prefix}")


def plain_text(markdown):
    """手順説明の装飾だけを除き、URLと安全条件を残す。"""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", markdown)
    return text.replace("**", "").replace("`", "").strip()


def practice_sections(text, prefix, allowed_headings):
    """指定した手順節だけを抽出する。回答・メモ・検証記録は対象外。"""
    sections = []
    heading_pattern = r"^## ([^\n]+)\n(.*?)(?=^## |\Z)"
    for heading, content in re.findall(heading_pattern, text, re.M | re.S):
        if not any(heading.startswith(allowed) for allowed in allowed_headings):
            continue
        if any(word in heading for word in ("学習メモ", "回答", "実装時")):
            raise ValueError(f"個人記録は実習へ抽出できません: {heading}")
        parts = re.split(r"^### ([^\n]+)\n", content, flags=re.M)
        introduction = parts[0].strip()
        subsections = [(heading, introduction)] if len(parts) == 1 else [
            (subheading, introduction + "\n\n" + subcontent)
            for subheading, subcontent in zip(parts[1::2], parts[2::2])
        ]
        for subheading, subcontent in subsections:
            blocks = list(re.finditer(r"```([^\n]*)\n(.*?)```", subcontent, re.S))
            body = plain_text(subcontent[:blocks[0].start()] if blocks else subcontent)
            steps = []
            for index, block in enumerate(blocks):
                next_start = blocks[index + 1].start() if index + 1 < len(blocks) else len(subcontent)
                after = plain_text(subcontent[block.end():next_start])
                language = {"powershell": "PowerShell", "bash": "Bash", "text": "共通コマンド"}.get(block.group(1).strip(), "コマンド")
                steps.append(dict(
                    title=f"手順 {index + 1} / {language}",
                    description="リポジトリ直下で、説明と実行条件を確認してから手動実行してください。",
                    command=block.group(2).strip(),
                    expected=after,
                ))
            entry = dict(
                id=f"{prefix}-{len(sections) + 1}", kind="practice",
                title=f"実習: {subheading}", body=body,
                callout="手順は原本から抽出しています。閲覧だけでは実行されません。既存環境がある場合は初回構築を繰り返さず、操作対象とデータへの影響を先に確認してください。",
            )
            if steps:
                entry["steps"] = steps
            sections.append(entry)
    return sections


def concept(term, description, analogy):
    return {"term": term, "description": description, "analogy": analogy}


def section(key, title, body, callout=None, steps=None):
    result = {"id": key, "title": title, "body": body}
    if callout:
        result["callout"] = callout
    if steps:
        result["steps"] = steps
    return result


def step(title, description, command, expected):
    return dict(title=title, description=description, command=command, expected=expected)


NAMESPACED_RESOURCES = {
    "pod", "deployment", "replicaset", "service", "job", "statefulset", "pvc",
    "configmap", "secret", "hpa", "networkpolicy", "serviceaccount", "role",
}


def diagram_node(key, label, resource, sublabel, group=None, column=0, contains=None):
    result = dict(id=key, label=label, resource=resource, kind=resource.rsplit(".", 1)[-1], sublabel=sublabel, column=column)
    if group:
        result["group"] = group
    if resource.startswith("kubernetes.") and resource.split(".")[1] in NAMESPACED_RESOURCES:
        result["namespace"] = "workboard"
    if contains:
        result["contains"] = contains
    return result


def relation(source, target, label, kind="traffic"):
    return {"from": source, "to": target, "label": label, "relation": kind}


def diagram_group(key, label, kind, parent=None):
    result = dict(id=key, label=label, kind=kind)
    if parent:
        result["parentId"] = parent
    return result


def diagram_view(key, title, description, nodes, relations):
    return dict(id=key, title=title, description=description, nodeIds=nodes, relations=relations)


def diagram_model(kind, title, caption, nodes, edges, groups=None, views=None, simulation=None):
    result = dict(type=kind, title=title, caption=caption, nodes=nodes, edges=edges, groups=groups or [])
    result["views"] = views or [diagram_view("overview", "全体像", caption, [n["id"] for n in nodes], sorted({e["relation"] for e in edges}))]
    if simulation:
        result["simulation"] = simulation
    return result


def k8s_groups(node_label="単一 Node / control-plane 兼 worker"):
    return [
        diagram_group("host", "ホスト上のブラウザー", "external"),
        diagram_group("cluster", "Kubernetes クラスター", "cluster"),
        diagram_group("namespace", "Namespace: workboard（論理スコープ）", "namespace", "cluster"),
        diagram_group("management", "API に保存される宣言・管理オブジェクト", "management", "namespace"),
        diagram_group("runtime", node_label, "node", "cluster"),
    ]


def pod(key, label, technology, column=0, group="runtime", temporary_data=False):
    containers = [dict(label="postgres" if technology == "PostgreSQL" else key.removesuffix("-pod"), technology=technology, resource="container")]
    if temporary_data:
        containers.append(dict(label="db-data", technology="emptyDir / この Pod の寿命", resource="storage.emptydir"))
    return diagram_node(key, label, "kubernetes.pod", "コンテナを実行する単位", group, column, containers)


def phase_diagram(phase_id):
    if phase_id == 0:
        nodes = [
            diagram_node("design", "一次設計書", "document", "目的と範囲", column=0),
            diagram_node("tools", "環境確認", "terminal", "CLI の導入と稼働を区別", column=1),
            diagram_node("observe", "観察メモ", "document", "実測した結果と未検証", column=2),
            diagram_node("adr", "設計課題 / ADR", "document", "理由・代替案・影響", column=3),
        ]
        edges = [relation("design", "tools", "必要条件", "configuration"), relation("tools", "observe", "実測", "configuration"), relation("observe", "adr", "判断の根拠", "configuration")]
        return diagram_model("foundation", "問いから次の判断へ", "学習の情報整理を示す図です。Kubernetes の実行環境ではありません。", nodes, edges)
    if phase_id == 1:
        groups = [diagram_group("host", "ホスト上のブラウザー", "external"), diagram_group("compose", "Docker Engine / Compose ネットワーク", "external")]
        nodes = [diagram_node("browser", "ブラウザー", "browser", "ホストの localhost:8080", "host")]
        for column, (key, label, technology) in enumerate([("web", "Web コンテナ", "Nginx"), ("api", "API コンテナ", "FastAPI"), ("db", "DB コンテナ", "PostgreSQL"), ("migration", "migration コンテナ", "Alembic / 正常終了")]):
            nodes.append(diagram_node(key, label, "container", technology, "compose", column))
        nodes.append(diagram_node("volume", "named volume", "storage.volume", "コンテナを削除しても残る保存領域", "compose", 2))
        edges = [relation("browser", "web", "HTTP :8080"), relation("web", "api", "/api/ HTTP"), relation("api", "db", "SQL :5432"), relation("db", "volume", "保存", "storage"), relation("migration", "db", "SQL / スキーマ準備"), relation("db", "migration", "DB healthy", "control"), relation("migration", "api", "終了コード 0", "control"), relation("api", "web", "API ready", "control")]
        views = [diagram_view("traffic", "通信と保存", "実線は HTTP/SQL。保存の線は DB と named volume の対応です。Kubernetes の Pod や Service はまだありません。", ["browser", "web", "api", "db", "volume"], ["traffic", "storage"]), diagram_view("startup", "起動条件", "Compose が準備状態と migration の終了を待ちます。破線は HTTP 通信ではありません。", ["db", "migration", "api", "web"], ["control"])]
        return diagram_model("compose", "コンテナ間の通信と保存先", "ブラウザーはコンテナではありません。Compose の範囲とホストを分けて示します。", nodes, edges, groups, views, dict(api=["api"], database=["db", "volume"], migration=["migration"]))
    if phase_id == 2:
        nodes = [diagram_node("browser", "ブラウザー", "browser", "ホストの localhost:8080", "host")]
        edges = [relation("browser", "web-service", "転送対象の指定", "configuration"), relation("browser", "web-pod", "HTTP / port-forward"), relation("web-service", "web-pod", "selector", "configuration")]
        for column, (key, title, technology) in enumerate([("web", "Web", "Nginx"), ("api", "API", "FastAPI"), ("db", "DB", "PostgreSQL")]):
            nodes.extend([
                diagram_node(f"{key}-service", f"{title} Service", "kubernetes.service", "Pod 外の論理的な接続先", "namespace", column),
                diagram_node(f"{key}-deployment", f"{title} Deployment", "kubernetes.deployment", "workboard-postgres" if key == "db" else f"workboard-{key}", "management", column),
                diagram_node(f"{key}-rs", f"{title} ReplicaSet", "kubernetes.replicaset", "必要な Pod 数を維持する宣言", "management", column),
                pod(f"{key}-pod", f"{title} Pod", technology, column, temporary_data=key == "db"),
            ])
            edges.extend([relation(f"{key}-deployment", f"{key}-rs", "所有", "ownership"), relation(f"{key}-rs", f"{key}-pod", "所有 / Pod 数の維持", "ownership")])
        nodes.extend([diagram_node("migrate-job", "migration Job", "kubernetes.job", "workboard-migrate / 通常 Complete", "management", 3), pod("migrate-pod", "migration Pod", "Alembic / 通常は実行終了", 3)])
        edges.extend([relation("migrate-job", "migrate-pod", "所有 / 完了を追跡", "ownership"), relation("migrate-pod", "db-service", "SQL / スキーマ準備"), relation("web-pod", "api-service", "/api/ HTTP"), relation("api-service", "api-pod", "HTTP / selector"), relation("api-pod", "db-service", "SQL :5432"), relation("db-service", "db-pod", "SQL / selector")])
        views = [
            diagram_view("traffic", "通信の経路", "実線は HTTP/SQL。port-forward は Service を指定して選んだ Web Pod へのトンネルで、ClusterIP 自体の外部公開ではありません。Deployment/ReplicaSet は通信を中継しません。", ["browser", "web-service", "web-pod", "api-service", "api-pod", "db-service", "db-pod"], ["traffic", "configuration"]),
            diagram_view("management", "管理と所有", "破線は API オブジェクトの所有関係です。Deployment/ReplicaSet はコンテナではなく宣言で、Control Plane のコントローラーがこの状態を調整します。Job の Pod は通常終了済みです。", [f"{key}-{suffix}" for key in ("web", "api", "db") for suffix in ("deployment", "rs", "pod")] + ["migrate-job", "migrate-pod"], ["ownership"]),
            diagram_view("database", "DB の寿命と初期化", "DB Pod 内の emptyDir はその Pod と一緒に失われます。Job の再実行はスキーマの再作成であり、タスクの復元ではありません。", ["api-pod", "db-service", "db-pod", "migrate-job", "migrate-pod"], ["traffic", "ownership"]),
        ]
        caption = "Node は実行場所、Namespace は論理スコープで、親子関係ではありません。Node 枠内の Pod も workboard Namespace に属します。kind は単一の control-plane 兼 worker です。"
        return diagram_model("kubernetes", "通信・管理・データの寿命を分ける", caption, nodes, edges, k8s_groups(), views, dict(api=["api-pod"], database=["db-pod"], migration=["migrate-job", "migrate-pod"]))
    if phase_id == 3:
        nodes = [pod("api-pod", "API Pod", "FastAPI", 0), diagram_node("db-service", "DB Service", "kubernetes.service", "安定した論理接続先", "namespace", 1), pod("db-pod", "DB Pod", "PostgreSQL", 1), diagram_node("sts", "DB StatefulSet", "kubernetes.statefulset", "Pod の識別子と保存先の対応", "management", 1), diagram_node("pvc", "PVC", "kubernetes.pvc", "Namespace 内の保存先要求", "namespace", 2), diagram_node("pv", "PV", "kubernetes.pv", "cluster scope の保存領域オブジェクト", "cluster", 2), diagram_node("config", "ConfigMap", "kubernetes.configmap", "設定値", "namespace", 0), diagram_node("secret", "Secret", "kubernetes.secret", "配布権限・保存時保護は別途必要", "namespace", 1)]
        edges = [relation("api-pod", "db-service", "SQL"), relation("db-service", "db-pod", "SQL / selector"), relation("sts", "db-pod", "所有 / 安定した識別子", "ownership"), relation("db-pod", "pvc", "mount に使用", "storage"), relation("pvc", "pv", "バインド", "storage"), relation("config", "api-pod", "設定を注入", "configuration"), relation("secret", "api-pod", "接続情報を配布", "configuration"), relation("secret", "db-pod", "接続情報を配布", "configuration")]
        views = [diagram_view("storage", "保存先とスコープ", "予習の DB 周辺図です。StatefulSet は ReplicaSet を介しません。PVC は Namespace 内、PV と Node は cluster scope です。PV は物理ディスクそのものの絵ではありません。", ["api-pod", "db-service", "db-pod", "sts", "pvc", "pv"], ["traffic", "ownership", "storage"]), diagram_view("configuration", "設定の配布", "予習。ConfigMap/Secret は実行中のコンテナではなく、API に保存される設定オブジェクトです。", ["config", "secret", "api-pod", "db-pod"], ["configuration"])]
        return diagram_model("storage", "Pod の寿命と保存先を分離する", "Phase 3 の予習です。API の管理チェーンなど、今回の焦点以外は省略しています。Node と Namespace は直交します。", nodes, edges, k8s_groups("保存先を利用する Node / 詳細は実装時に決定"), views, dict(api=["api-pod"], database=["db-pod", "pvc", "pv"], migration=[]))
    if phase_id == 4:
        groups = k8s_groups("Node A / 実行場所") + [diagram_group("node-b", "Node B / 実行場所", "node", "cluster")]
        nodes = [diagram_node("metrics", "CPU 指標", "document", "metrics-server 等から得る値", "cluster", 0), diagram_node("hpa", "HPA", "kubernetes.hpa", "replicas を調整する宣言", "management", 0), diagram_node("deploy", "API Deployment", "kubernetes.deployment", "更新方針と必要数", "management", 1), diagram_node("rs", "API ReplicaSet", "kubernetes.replicaset", "Pod 数を維持", "management", 1), diagram_node("service", "API Service", "kubernetes.service", "準備できた Pod を選択", "namespace", 0), pod("api-a", "API Pod A", "FastAPI", 0), pod("api-b", "API Pod B", "FastAPI", 0, "node-b")]
        edges = [relation("metrics", "hpa", "判断材料", "configuration"), relation("hpa", "deploy", "replicas を調整", "control"), relation("deploy", "rs", "所有", "ownership"), relation("rs", "api-a", "所有", "ownership"), relation("rs", "api-b", "所有", "ownership"), relation("service", "api-a", "HTTP"), relation("service", "api-b", "HTTP")]
        views = [diagram_view("traffic", "通信と配置", "予習の API 拡大図です。Service は Node 内のプロセスではありません。2 Pod が異なる Node に配置される条件は別途設計が必要です。", ["service", "api-a", "api-b"], ["traffic"]), diagram_view("control", "数を調整する関係", "指標→HPA→Deployment は制御。Deployment→ReplicaSet→Pod は所有関係です。HPA は Node 台数を直接増やしません。", ["metrics", "hpa", "deploy", "rs", "api-a", "api-b"], ["configuration", "control", "ownership"])]
        return diagram_model("scaling", "通信・レプリカ制御・Node 配置", "Phase 4 の予習。API 部分の拡大図で、DB/Web は省略しています。", nodes, edges, groups, views)
    if phase_id == 5:
        nodes = [diagram_node("user", "利用者", "identity", "Kubernetes API を操作する主体", "host"), diagram_node("sa", "ServiceAccount", "kubernetes.serviceaccount", "ワークロードの API アクセス主体", "namespace", 0), diagram_node("role", "Role / RoleBinding", "kubernetes.role", "Namespace 内の認可設定", "management", 1), diagram_node("kapi", "Kubernetes API", "kubernetes.api", "Control Plane の API", "cluster", 2), pod("web-pod", "Web Pod", "Nginx", 0), diagram_node("api-service", "API Service", "kubernetes.service", "HTTP の接続先", "namespace", 1), pod("api-pod", "API Pod", "FastAPI", 1), diagram_node("policy", "NetworkPolicy", "kubernetes.networkpolicy", "対応 CNI が適用する通信規則", "namespace", 2)]
        edges = [relation("user", "kapi", "API 操作要求", "control"), relation("sa", "kapi", "Pod の API 要求", "control"), relation("role", "kapi", "認可条件", "configuration"), relation("web-pod", "api-service", "HTTP"), relation("api-service", "api-pod", "HTTP"), relation("policy", "api-pod", "許可・拒否の設定", "configuration")]
        views = [diagram_view("authorization", "操作する権限", "予習。RBAC は API に何を要求できるかを決めます。ServiceAccount はコンテナではありません。", ["user", "sa", "role", "kapi"], ["configuration", "control"]), diagram_view("network", "アプリの通信", "実線が HTTP。NetworkPolicy 自体が通信を中継するのではなく、対応 CNI がルールを適用します。", ["web-pod", "api-service", "api-pod", "policy"], ["traffic", "configuration"])]
        return diagram_model("security", "API 権限とアプリ通信を分ける", "Phase 5 の予習。Namespace の権限と Pod の実行場所を区別して描きます。", nodes, edges, k8s_groups(), views)
    if phase_id == 6:
        groups = [diagram_group("outside", "構成を定義する利用者", "external"), diagram_group("aws", "AWS 環境 / 責任の分担", "aws"), diagram_group("cluster", "EKS / Kubernetes クラスター", "cluster", "aws"), diagram_group("managed-control", "AWS が運用する Control Plane", "aws", "cluster"), diagram_group("runtime", "Managed Node Group / EC2 上の Node", "node", "cluster")]
        nodes = [diagram_node("tf", "Terraform", "document", "利用者が構成と差分を管理", "outside", 0), diagram_node("vpc", "VPC / subnet", "aws.vpc", "利用者が経路・アクセス範囲を設計", "aws", 0), diagram_node("eks", "EKS Control Plane", "aws.eks", "AWS が運用・利用者がアクセス設定", "managed-control", 1), diagram_node("ecr", "ECR", "aws.ecr", "クラスター外のイメージ保管", "aws", 2), pod("web-pod", "Web Pod", "Nginx", 0), pod("api-pod", "API Pod", "FastAPI", 1)]
        edges = [relation("tf", "vpc", "構成を定義", "configuration"), relation("tf", "eks", "構成を定義", "configuration"), relation("eks", "web-pod", "配置・状態の調整", "control"), relation("eks", "api-pod", "配置・状態の調整", "control"), relation("ecr", "web-pod", "イメージを配布", "configuration"), relation("ecr", "api-pod", "イメージを配布", "configuration")]
        return diagram_model("eks", "AWS 管理と利用者の責任", "Phase 6 の将来案。標準 EKS の Control Plane は AWS が運用します。Managed Node Group でも Node/AMI 更新方針・アドオン・アプリ設定は利用者の責任として残ります。枠は実行配置と責任の説明で、VPC が Control Plane 全体を包含するという意味ではありません。", nodes, edges, groups)
    if phase_id == 7:
        groups = k8s_groups("EKS の Node / 利用者のワークロード")
        groups.insert(1, diagram_group("aws", "AWS マネージドサービス", "aws"))
        next(group for group in groups if group["id"] == "cluster")["parentId"] = "aws"
        nodes = [diagram_node("browser", "ブラウザー", "browser", "制限した検証アクセス", "host", 0), diagram_node("alb", "ALB", "aws.alb", "クラスター外の HTTP 入口", "aws", 0), diagram_node("rds", "RDS PostgreSQL", "aws.rds", "クラスター外の DB", "aws", 2), diagram_node("iam", "IAM role", "aws.iam", "Controller の ALB 管理権限", "aws", 3), diagram_node("ingress", "Ingress 定義", "document", "Kubernetes API に保存する入口の宣言", "management", 0), diagram_node("web-service", "Web Service", "kubernetes.service", "ターゲットを選ぶ backend 定義", "namespace", 0), diagram_node("api-service", "API Service", "kubernetes.service", "内部 HTTP 接続先", "namespace", 1), pod("web-pod", "Web Pod", "Nginx", 0), pod("api-pod", "API Pod", "FastAPI", 1), pod("lbc-pod", "Controller Pod", "AWS Load Balancer Controller", 3)]
        nodes[-5]["namespace"] = "workboard"  # Ingress も namespaced な API オブジェクト。
        edges = [relation("browser", "alb", "HTTP / 制限付き"), relation("alb", "web-pod", "HTTP / IP ターゲット案"), relation("web-pod", "api-service", "/api/ HTTP"), relation("api-service", "api-pod", "HTTP"), relation("api-pod", "rds", "SQL"), relation("web-service", "web-pod", "selector", "configuration"), relation("ingress", "web-service", "backend を宣言", "configuration"), relation("ingress", "lbc-pod", "監視する定義", "configuration"), relation("lbc-pod", "alb", "作成・更新を要求", "control"), relation("iam", "lbc-pod", "AWS API 権限", "configuration")]
        views = [diagram_view("traffic", "HTTP と SQL の経路", "将来の IP ターゲット案を例示。ALB は選ばれた Web Pod へ転送します。Service はターゲット選択の論理設定で、Controller はリクエストを中継しません。実装時に方式を確定します。", ["browser", "alb", "web-service", "web-pod", "api-service", "api-pod", "rds"], ["traffic", "configuration"]), diagram_view("control", "ALB を管理する関係", "Ingress は宣言、Controller Pod は実行中のプログラム、ALB は AWS の別サービスです。Controller はクラスター外の ALB を管理できるため、実行場所と管理対象の境界は一致しません。", ["ingress", "web-service", "lbc-pod", "alb", "iam"], ["control", "configuration"])]
        return diagram_model("integration", "Kubernetes と AWS サービスの連携", "Phase 7 の予習。RDS/ALB/IAM は Kubernetes Pod ではありません。IAM 図は Controller の AWS API 操作権限で、アプリの RDS SQL 認証とは別です。", nodes, edges, groups, views)
    if phase_id == 8:
        nodes = [diagram_node("git", "Git の変更", "document", "構成の正本", column=0), diagram_node("ci", "CI", "pipeline", "テスト・ビルド", column=1), diagram_node("approve", "承認", "document", "反映するかの判断", column=2), diagram_node("cd", "CD / GitOps", "pipeline", "方式を比較して選ぶ", column=3), diagram_node("app", "対象環境", "document", "構成と実状態の照合先", column=4), diagram_node("observe", "ログ・指標", "document", "SLI と復旧判断", column=5)]
        edges = [relation("git", "ci", "検査", "configuration"), relation("ci", "approve", "結果", "configuration"), relation("approve", "cd", "反映を許可", "control"), relation("cd", "app", "更新", "control"), relation("app", "observe", "計測結果", "configuration"), relation("observe", "git", "改善", "configuration")]
        return diagram_model("pipeline", "変更から次の改善へ", "Phase 8 の予習。これは工程と情報の流れで、箱がすべて Kubernetes リソースやコンテナという意味ではありません。", nodes, edges)
    nodes = [diagram_node("requirements", "想定要件", "document", "規模・チーム・SLO", column=0), diagram_node("ecs", "ECS 案", "aws.ecs", "構成と運用の選択肢", column=1), diagram_node("eks", "EKS 案", "aws.eks", "構成と運用の選択肢", column=2), diagram_node("compare", "比較表", "document", "費用・責任・移植性", column=3), diagram_node("adr", "採用 ADR", "document", "理由・反対案・不確実性", column=4)]
    edges = [relation("requirements", "ecs", "同じ要件", "configuration"), relation("requirements", "eks", "同じ要件", "configuration"), relation("ecs", "compare", "根拠", "configuration"), relation("eks", "compare", "根拠", "configuration"), relation("compare", "adr", "判断", "configuration")]
    return diagram_model("comparison", "要件から根拠ある選定へ", "サービスの比較を表す概念図です。EKS の採用やクラスターの構築が完了したという意味ではありません。", nodes, edges)


RUBRICS = [
    [
        ["Kubernetes自体の学習とAWS固有の学習を段階的に分ける", "クラウド費用・構成要素の増加を説明する"],
        ["CLI導入とエンジン/接続の稼働を区別する", "確認できた事実と未検証を分ける"],
        ["更新漏れと正本不明の問題を説明する", "一次情報を一か所で管理する理由を述べる"],
        ["ignoreは今後の追跡対象を制御するものと説明する", "既存履歴や追跡済み秘密値は消えないと説明する"],
    ],
    [
        ["更新・再起動・役割を独立して管理できると説明する", "コンテナ分割だけで冗長化やマイクロサービス化が完成するわけではないと理解する"],
        ["起動順とSQL受付可能な状態を区別する", "service_healthyとmigration正常終了の条件を区別し稼働中の接続保証ではないと説明する"],
        ["localhostはAPIコンテナ自身を指す", "DBへの接続はDBサービス名とポートを使う"],
        ["APIは処理を行いDBがデータを保持すると説明する", "PostgreSQLのnamed volumeがコンテナ外で残ると説明する"],
        ["DB障害でAPI再起動を繰り返す無意味な連鎖を説明する", "liveはプロセス、readyは受付可否と区別する"],
    ],
    [
        ["Podはコンテナの実行単位と説明する", "Deployment→ReplicaSet→Podの制御と置き換えを説明する"],
        ["Podの置き換えで名前やIPが変わり得る", "Serviceの安定した名前とselectorによる転送先選択を説明する"],
        ["対象Podが選ばれずEndpointSliceに期待する転送先がないと説明する", "PodがRunningでもService通信が成功するとは限らないと説明する"],
        ["API Pod削除では独立したDBのデータは残る", "DB Pod削除ではemptyDirとスキーマが消えmigrationの再実行が必要と説明する"],
        ["Kubernetesはコントローラーが継続的に望ましい状態へ近づける", "Composeの起動操作や再起動ポリシーとKubernetesの継続的な制御を区別する"],
    ],
    [["安定した識別子とストレージを扱うStatefulSetの用途を説明する", "StatefulSetだけでバックアップやDBの高可用性は完成しないと説明する"], ["Podの寿命から保存先を分離すると説明する", "ノード喪失・誤削除・バックアップの課題を区別する"], ["overlayはbaseのYAMLへのパッチで環境差分を表すと説明する", "変数展開や条件分岐を行うテンプレートエンジンではなく、存在しないリソースを自動では作らないと説明する"]],
    [["同一ノードの障害で全レプリカが停止し得ると説明する", "ノードやAZへの分散とDBの単一障害点も考える"], ["HPAは主にワークロードのレプリカ数を調整すると説明する", "ノード容量の追加は別の仕組みであると説明する"]],
    [["Secretはbase64だけで秘密を保護できないと説明する", "APIアクセス権限・保存時の保護・配布先を含めて考える"], ["人とワークロードを区別し最小権限を考える", "操作の対象・範囲・監査の観点を説明する"], ["k9sはkubeconfigの資格情報でKubernetes APIを呼ぶクライアントであると説明する", "操作できる範囲はツールではなくRBACで決まり、TUIでも誤削除のリスクは同じと説明する"]],
    [["AWS管理のControl Planeと利用者側の責任を区別する", "ノード・アドオン・アプリの更新や設定責任を挙げる"], ["管理主体と観察可能な範囲を比較する", "費用・制約・学習目的を判断条件に含める"]],
    [["DB運用責任・バックアップ・障害対応の分離を説明する", "費用・AWS依存・接続設計とのトレードオフを挙げる"], ["DB接続失敗によりreadyが503になり得ると説明する", "liveはDB非依存でありスキーマの正常性は別確認と説明する"], ["chartのバージョンとvaluesを固定し、helm templateで生成されるリソースを確認すると説明する", "RBAC・Webhook・CRDなど権限や影響範囲の大きいリソースと、配布元の信頼性を確認する"]],
    [["Gitを正本として継続的に差分を調整する方式とCIによる直接実行を区別する", "権限・ドリフト・復旧方法を比較する"], ["対象数・チーム・運用能力という判断条件を挙げる", "管理要素の追加コストも比較し一律に断定しない"], ["Helmはパッケージ化・配布・release管理、Kustomizeは自分のYAMLの環境差分に向くと説明する", "利用者・配布の有無・レビューのしやすさを判断条件に含める"], ["生成手順が二段になり、最終的なマニフェストの出所と差分を追いにくくなると説明する", "併用する場合は役割の分担と生成結果の確認方法を決めると説明する"]],
]


def build():
    design = read(DESIGN)
    lab_texts = [read(path) for path in LABS]
    phase_texts = {
        int(match.group(1)): match.group(2)
        for match in re.finditer(r"^### Phase (\d+) — [^\n]*\n(.*?)(?=^### Phase |^## 7\.|\Z)", design, re.M | re.S)
    }
    phases = []

    def add(pid, slug, title, subtitle, level, minutes, summary, concepts, sections, graph):
        text = lab_texts[pid] if pid < 3 else phase_texts[pid]
        if pid < 3:
            goals = re.findall(r"^- (.+)$", heading_body(text, "学習目標"), re.M)
            prompts = lab_questions(text)
            labels = memo_labels(text)
            rubrics = RUBRICS[pid]
            if pid == 1:
                sections.extend(practice_sections(
                    read("README.md"), "practice-setup",
                    ["Phase 1: Compose 上で WorkBoard を起動する"],
                ))
            sections.extend(practice_sections(
                text, "practice-lab",
                ["前提条件", "検証コマンド・期待結果", "故障実験", "失敗時に確認すること", "Linux / macOS / WSL での再現", "後片付け"],
            ))
        elif pid < 9:
            learned = re.search(r"\*\*学ぶこと:\*\* (.+)", text).group(1)
            goals = [learned, "実装前に設計条件と検証方法を説明できる"]
            question_line = re.search(r"\*\*設計の問い:\*\* (.+)", text).group(1)
            prompts = [q.strip() for q in re.findall(r"[^？]+？", question_line)]
            rubrics = RUBRICS[pid]
            labels = ["理解した概念", "想定する構成と採用理由", "必要な実験と期待結果", "疑問・未解決事項"]
        else:
            goals = ["ECSとEKSを同じ要件で比較できる", "採用理由・反対案・不確実性を根拠と共に残せる"]
            pairs = [
                (axis, question)
                for axis, question in re.findall(r"^\| ([^|]+) \| ([^|]+) \|$", text, re.M)
                if axis.strip() not in {"軸", "---"}
            ]
            prompts = [f"{axis.strip()}: {question.strip()}" for axis, question in pairs]
            rubrics = [["ECSとEKSを同じ条件で比較する", f"{axis.strip()}について構成・運用の違いを根拠と共に説明する", "前提と不確実性を明示しEKSを無条件の正解としない"] for axis, _ in pairs]
            labels = ["想定要件", "比較結果と根拠", "採用案・反対案", "不確実性と追加調査"]
        if pid >= 3:
            sections.insert(0, section("preview", "この章は予習です", "Phase 3以降のラボは未実装です。ここでは設計書の計画をもとに構成と判断軸を学びます。\n\nコマンドの実行や完了済みの実験を前提にせず、これから何を観察すべきかを回答してください。", "AWSリソース作成や既存環境の変更は、この教材の閲覧・回答では行いません。"))
        assert len(prompts) == len(rubrics), (pid, prompts)
        phases.append(dict(
            id=pid, slug=slug, title=title, subtitle=subtitle, level=level,
            implemented=pid < 3, estimatedMinutes=minutes, summary=summary,
            goals=goals, concepts=concepts, sections=sections, diagram=graph,
            questions=[dict(id=f"q{i}", prompt=prompt, rubric=rubric) for i, (prompt, rubric) in enumerate(zip(prompts, rubrics), 1)],
            memoFields=[dict(id=f"m{i}", label=label) for i, label in enumerate(labels, 1)],
            sources=[dict(label="一次設計書", path=DESIGN)] + ([dict(label=f"Lab {pid:02d} 原本", path=LABS[pid])] if pid < 3 else []) + ([dict(label="Compose初回準備", path="README.md")] if pid == 1 else []),
        ))

    add(0, "foundation", "学習の土台を整える", "環境確認と設計判断の記録", "foundation", 25,
        "何が使えるかを確かめ、事実と未検証を分けて記録します。", [
            concept("preflight", "後の作業に必要なツールを参照のみで確認する準備点検です。", "出発前に道具をそろえる点検表"),
            concept("ADR", "採用した案・代替案・理由・影響を残す短い設計記録です。", "後から判断をたどれる議事録"),
            concept("一次設計書", "方針の原本を一か所で管理し、入口の文書から参照します。", "地図の正本と案内板"),
        ], [
            section("start", "二つの画面を使い分ける", "このポータルは学習・回答用の localhost:8765、WorkBoardはタスク操作用の localhost:8080 です。ポータルを開いてもWorkBoardやkindを起動・停止しません。\n\n各章で解説と図を読み、実際の観察は学習メモへ、設計判断は設計課題へ書きます。採点への送信では、何を実行し何を省略したかも伝えてください。"),
            section("check", "導入と稼働を分けて確認する", "バージョンが返ればCLIの実行は確認できます。Dockerエンジンの起動、DB接続、WSL連携や互換性まで確認できたとは限りません。", steps=[step("PowerShellで確認", "リポジトリ直下で実行する参照のみの処理です。", command_from(lab_texts[0], "powershell -NoProfile"), "Gitが確認できれば終了コード0。他ツールの未導入も区別して表示。")]),
            section("record", "履歴と秘密情報を分ける", ".gitignoreは新たな追跡を避けるための設定です。追跡済みの秘密情報や過去の履歴は消しません。\n\n学習メモには観察・コマンド・期待との差を書きます。設計課題には自分の理由と代替案を書き、結果だけの『できた』から一歩進めます。", "補助解説はポータル独自の編集です。設計課題と学習メモの項目名は既存ラボを正本にしています。"),
        ], phase_diagram(0))

    add(1, "compose", "3層アプリを動かす", "Docker Compose とデータの寿命", "foundation", 45,
        "Web・API・DBの通信と、起動・準備完了・永続化の違いをつかみます。", [
            concept("コンテナとlocalhost", "コンテナごとにプロセスとネットワークの境界があります。API内のlocalhostはAPI自身です。", "別々の部屋で『この部屋』と呼ぶ感覚"),
            concept("Readiness", "リクエストを受け付けられるかを確認します。プロセス生存とは別の条件です。", "開店していることと注文に応えられることの違い"),
            concept("named volume", "DBコンテナを取り替えても残せる保存先です。volume自体を削除すれば保存データは失われます。", "部屋を引っ越しても持っていける収納箱"),
        ], [
            section("flow", "入口はWebだけ", "ブラウザーは8080番のNginxへ接続します。静的画面を受け取り、/api/の呼び出しはNginxがAPIへ転送します。APIはDBサービス名でPostgreSQLへ接続します。\n\nAPI/DBのポートをホストに公開しなくても、同じComposeネットワーク内では通信できます。コンテナを分ける主な理由は個別の更新・再起動・管理です。分割だけで冗長化が完成するわけではありません。"),
            section("startup", "起動順と準備完了は別", "DB→migration→API→Webの順に準備します。service_healthyはDBの準備条件、service_completed_successfullyはmigrationの正常終了を待つ条件です。\n\nこれは起動時の条件です。稼働中のDB障害では接続の回復やエラー処理が別途必要になります。migrationはテーブルを用意する一回の処理で、長時間リクエストを受けるAPIとは役割が異なります。", "現在kindを使用して8080を転送中なら、そのまま学習できます。Composeを重ねて起動せず、初回構築はこの章の実習を開いて進めてください。", [
                step("Composeの状態を読む", "既存コンテナを変更せず一覧を確認します。停止済みなら何も動いていないことが観察結果です。", command_from(lab_texts[1], "docker compose -f docker/compose.yaml ps -a"), "稼働中ならAPI/DBがhealthy、WebがUp、migrationがExited 0。"),
                step("準備の経過を読む", "migrationとAPIのログを参照します。", command_from(lab_texts[1], "docker compose -f docker/compose.yaml logs"), "migrationの正常終了とAPIの起動が分かる。")]),
            section("health", "healthと保存先を観察する", "LivenessはAPIの生存、ReadinessはDBへの接続を確認します。DB停止時にliveまで失敗させると、APIを再起動してもDB障害は直らず、再起動が連鎖し得ます。\n\nAPIやブラウザーを再起動してもタスクが残るのは、DBがnamed volumeに保存するためです。現在8080がkindを向いていれば、同じURLでも保存先はkindのDBです。異なる環境のデータを同じものと考えないでください。", steps=[step("現在の8080のhealthを見る", "返答の意味に加え、今の8080がComposeかkindかをメモします。", command_from(lab_texts[1], "Invoke-RestMethod http://localhost:8080/health/ready"), "DBに接続できれば正常応答。未起動なら接続失敗も観察結果。")]),
        ], phase_diagram(1))

    add(2, "kubernetes", "望ましい状態を保つ", "kind・Pod・Service・一時DB", "local", 60,
        "Podが置き換わっても通信できる理由と、データまで復旧するとは限らない理由を学びます。", [
            concept("Podとコンテナ", "PodはKubernetesの配置・実行の単位です。一つ以上のコンテナがネットワークとvolumeを共有します。", "同じ住所と共有設備を持つ作業室"),
            concept("Deployment", "ReplicaSetを通して指定数のPodを維持し、更新を管理します。Podが失われると別のPodを作ります。", "必要人数を補充する現場の管理者"),
            concept("ClusterIP Service", "selectorでPodを選び、クラスター内に安定した接続先を用意します。", "担当者が替わっても使える代表窓口"),
            concept("emptyDir", "Podに属する一時volumeです。コンテナの再起動を越えて残っても、Pod削除では消えます。", "同じ作業室の中だけで使える棚"),
            concept("JobとinitContainer", "Jobは完了を目指す一回の処理です。通常のinitContainerは同じPodの主コンテナより前に正常終了する必要があります。", "独立した準備作業と、開店前の室内準備の違い"),
        ], [
            section("observe", "既存クラスターから読み始める", "この環境のPhase 2は構築済みです。読み取りコマンドからPod・ReplicaSet・Deployment・Serviceを見比べます。各コマンドは専用contextを明示し、別クラスターと混同しないようにします。\n\nkindのNodeもローカルDocker内で動きます。Nodeの中にPod、その中にコンテナという階層です。アプリのコンテナイメージはComposeと共通でも、起動・維持する主体が変わります。", "以下は手動実行用です。ポータルはコマンドを自動実行しません。既存Podの削除や再構築はここでは必要ありません。", [
                step("現在のシェルへ専用設定", "先頭のドットとスペースは現在のPowerShellへ設定を読み込む指定です。", command_from(lab_texts[2], ". .\\scripts\\kind-env.ps1"), "現在のシェルだけで専用KUBECONFIGと.toolsが使える。"),
                step("管理階層を一覧にする", "作られたPodと、それを維持するリソースを見ます。", command_from(lab_texts[2], "kubectl --context kind-workboard-lab -n workboard get pods,rs,deploy,svc"), "Web/API/DBが各1 Pod。Serviceが別リソースとして存在。"),
                step("転送先を確かめる", "selectorとPod labelが一致する結果をEndpointSliceで追います。", command_from(lab_texts[2], "kubectl --context kind-workboard-lab -n workboard get endpointslices"), "API Serviceに対応するPodのアドレスが分かる。")]),
            section("network", "Serviceとport-forwardを分ける", "Web→APIの通信はClusterIP Serviceを利用します。ServiceのselectorとPodのlabelが一致しないと、期待するPodへ転送されません。PodがRunningであることだけでは通信の成功を保証しません。\n\nsvc/workboard-webを指定したport-forwardはselectorで選んだWeb Podへの一時トンネルです。ClusterIPそのものを外部公開する操作ではありません。WorkBoardはlocalhost:8080、学習ポータルはlocalhost:8765です。既存の転送を止めず、そのまま8080を利用できます。", "port-forwardは常設の公開設定ではありません。接続しているWeb Podの置き換えでも終了する場合があります。"),
            section("lifecycle", "再作成はデータ復元ではない", "API Podを削除するとDeploymentが新しいPodを補います。DB PodとそのemptyDirが残るのでタスクは保持されます。PodのUIDは変わりますが、IPは再利用される場合もあります。\n\nDB Podを削除すると、新しいemptyDirでDBが立ち上がります。タスクだけでなくスキーマも失われます。完了済みmigration JobはDB再作成だけでは再実行されません。Jobを再実行してスキーマを作り直しても、元データの復元にはなりません。", "DB削除実験はデータ消失を伴います。実行する場合はLab 02の条件・対象を確認し、失ってよいと判断してから別途行ってください。"),
            section("init", "initContainerで解ける範囲", "現在のPhase 2はmigration Jobを使っており、API PodにinitContainerはありません。比較として、initContainerは同じPodの主コンテナより前に順番に実行され、準備を終えてから主コンテナを起動できます。\n\nAPI PodのinitContainerでDBを準備したとしても、別のDB Podだけが再作成されたとき、既存API PodのinitContainerは自動で再実行されません。DB障害中の接続回復やmigrationの再実行方針は、別に設計する必要があります。\n\n/health/readyのSELECT 1はDB接続を確かめます。テーブルの存在やmigration完了まで調べるものではないので、readyが200でもCRUDが失敗する場面があります。"),
        ], phase_diagram(2))

    add_previews(add)
    validate(phases)
    return {"title": "WorkBoardで学ぶ Kubernetes / EKS", "phases": phases}


def add_previews(add):
    add(3, "storage", "設定とデータを切り離す", "予習 / StatefulSet・PVC・Secret", "local", 35,
        "Podがなくなっても守るデータと、別途必要な保護を整理します。", [
            concept("PVC / PV", "アプリの保存先要求と、それに応える保存領域を分けます。", "倉庫の利用申込書と割り当てられた棚"),
            concept("StatefulSet", "安定した識別子やストレージとの対応を持つPodを管理します。", "名前付きの担当席と専用保管庫"),
            concept("ConfigMap / Secret", "設定と秘密情報をアプリのイメージから分離します。Secretにも権限設計が必要です。", "共有手順書と配布先を絞った鍵"),
        ], [
            section("persistence", "Podの寿命を越える保存先", "emptyDirからPVCへ移すと、Podの置き換えと保存領域の寿命を分離できます。StatefulSetはDBの識別子や保存先の対応を扱いやすくしますが、バックアップやDB自体の可用性を自動で完成させません。\n\n設計書はStorageClassを事前確認する方針です。ローカルノードに依存する保存先なら、ノード喪失時の復旧は別課題になります。"),
            section("config", "設定差分を追える形にする", "Kustomizeのbaseに共通構成、overlayに環境差分を置く計画です。Secretに値を入れても、読み取り可能な人・Pod・保存時の保護は別途考えます。\n\n実装時には『Pod削除後に同じタスクが残るか』『PVCがどのPVに結び付くか』『誤削除から戻せるか』を別々に観察します。"),
        ], phase_diagram(3))

    add(4, "scaling", "増やす・更新する・耐える", "予習 / Probe・HPA・配置制御", "local", 35,
        "レプリカ数だけでは語れない可用性と、計測に基づく調整を学びます。", [
            concept("Probe", "生存・受付可否・起動の確認を目的ごとに分けます。", "呼吸確認・受付状況・開店準備の別々の点検"),
            concept("HPA", "指標をもとにワークロードのレプリカ数を調整します。", "注文数に応じた窓口人数の調整"),
            concept("requests / limits", "配置に必要な資源の見積もりと、利用の上限を設定します。", "予約した席数と使用可能な広さ"),
        ], [
            section("availability", "同じ場所に増やすだけでは足りない", "APIを3 Podにしても同じNodeに載っていれば、そのNodeの故障で全て止まり得ます。ノードやAZへの分散、DBの単一障害点、更新時に残す受付能力を組み合わせて考えます。\n\nPDBは自発的な中断の許容数を扱う仕組みです。突然のNode故障まで防止する保証ではありません。"),
            section("measurement", "測ってから数値を決める", "HPAのための指標を得るにはmetrics-server等の前提が必要です。CPU負荷・応答時間・Pod数・イベントを同じ時間軸で記録して判断します。\n\nRolling Updateとrollbackでは、更新中のHTTP応答と残っているPod数を観察します。動いていない実験の復旧時間を推測で記録しないことが大切です。"),
        ], phase_diagram(4))

    add(5, "security", "権限と通信を絞る", "予習 / RBAC・NetworkPolicy・診断", "local", 35,
        "誰が何をできるかと、どこへ通信できるかを別々に考えます。", [
            concept("RBAC", "Kubernetes APIへの操作権限を役割と関連付けます。", "役職ごとの操作許可証"),
            concept("ServiceAccount", "Pod内の処理がKubernetes APIを利用するときの主体です。", "作業員本人とは別の設備用身分証"),
            concept("NetworkPolicy", "対応CNIのもとでPod間等の通信許可を制御します。", "部屋の間に置く通行ルール"),
        ], [
            section("boundaries", "権限と通信は別の境界", "RBACでAPI操作を制限しても、アプリの通信まで自動的に閉じるわけではありません。NetworkPolicyを定義しても、CNIが処理しなければ期待どおりに遮断されません。\n\nSecretの読み取り権限、実行ユーザー、コンテナ権限、イメージを合わせて考えます。"),
            section("diagnose", "症状から層を切り分ける", "イメージ取得失敗ならイベントとタグ、通信失敗ならselector・EndpointSlice・DNS、権限不足なら主体とRoleBindingを追います。\n\n実装時には再現条件・観察したログ・原因・復旧手順をRunbookに残す計画です。通信を拒否できたという結論には、許可と拒否の両方の試験が必要です。"),
        ], phase_diagram(5))

    add(6, "eks", "AWS上の責任を分ける", "予習 / VPC・EKS・Node・Terraform", "cloud", 40,
        "マネージドサービスでも残る責任と、費用・公開範囲を設計します。", [
            concept("EKS", "AWS管理のKubernetes Control Planeを利用するサービスです。", "建物管理を任せても利用者の仕事は残る職場"),
            concept("Managed Node Group", "EC2ノード群の管理を支援します。利用者には構成や更新の判断が残ります。", "設備の交換を支援する管理契約"),
            concept("Terraform", "インフラの望む構成と差分をコードで扱います。", "建設図面と工事前の差分表"),
        ], [
            section("responsibility", "まず標準EKSで境界を見る", "設計書は最初に標準EKSとManaged Node Groupsを使い、Control Plane・Node・アドオン・アプリの担当範囲を観察する方針です。Auto Modeは後で管理主体や費用を比較する課題です。\n\nAWSに任せる部分と、自分で監視・更新・設定する部分を表にしてみましょう。"),
            section("cost", "構築より前に決める条件", "region、AZ、Node、NAT、endpointのアクセス範囲、利用時間、削除後に残る資産を整理します。EKS料金だけでなくEC2・ALB・RDS・NAT等も見積もる必要があります。\n\n開始条件は利用の明示承認、見積もり確認、予算通知、クリーンアップ手順のレビューです。予算通知は課金停止の保証ではありません。", "この章には実行コマンドを掲載していません。まだTerraform構成もAWSリソースも作成していません。"),
        ], phase_diagram(6))

    add(7, "integration", "AWSサービスをつなぐ", "予習 / ALB・RDS・Pod Identity", "cloud", 35,
        "入口・データ・権限をマネージドサービスとどう分担するか考えます。", [
            concept("ALB / Controller", "Ingressの定義をControllerが処理してALBを管理します。", "受付方針と、それを設備へ反映する管理者"),
            concept("RDS", "DBの運用機能をAWSへ任せる選択肢です。接続やデータ保護の設計は必要です。", "保管業務を専門業者と分担する倉庫"),
            concept("Pod Identity", "PodからAWSを呼ぶ際に、限定したIAM権限を渡す仕組みです。", "用途を絞った作業用の許可証"),
        ], [
            section("path", "入口とDBをクラスターの外へ", "ALB→Web→API→RDSという経路を設計します。ALBのIngressを扱うAWS Load Balancer Controllerと、IngressというAPIリソースは別です。\n\nRDSはDB運用を分担できますが、費用・AWS依存・ネットワーク接続・移行・復旧の検討が増えます。バックアップの取得だけでなく復元方法まで比較します。"),
            section("identity", "公開と権限を限定する", "認証のないWorkBoardを恒常的にインターネットへ公開しない方針です。短時間の検証でも公開範囲・セキュリティグループ・後片付けを先に決めます。\n\nCSVをS3に置く発展課題では、Pod Identityで必要な操作だけを許可する計画です。S3やWorkerは任意の発展課題で、MVPの必須構成ではありません。"),
        ], phase_diagram(7))

    add(8, "pipeline", "変更と運用をつなぐ", "予習 / CI・CD・GitOps・SLI", "review", 35,
        "変更を安全に届け、観察し、戻すまでを一つの流れで考えます。", [
            concept("CI / CD", "変更の検査と、環境への反映を分けて設計します。", "出荷検査と配送の工程"),
            concept("GitOps", "Gitの定義と実環境の差を継続的に調整する運用方式です。", "正本の台帳と現物を定期照合する係"),
            concept("SLI / SLO", "利用者視点の指標と、その目標値を分けて定義します。", "測った所要時間と約束する所要時間"),
        ], [
            section("delivery", "テスト・反映・復旧を切り分ける", "CIでlint・APIテスト・イメージビルド・構文確認を行い、CDは最初に手動承認制とする計画です。GitOpsは対象数や運用能力を踏まえて方式比較後に追加します。\n\n失敗した変更をどこで止めるか、認証情報をどこへ渡すか、どの版へ戻すかも設計対象です。"),
            section("observe", "測った事実で改善する", "応答時間、HTTPエラー率、再起動、資源使用量を観察します。成功率やp95応答時間をSLIとし、期間と母数を含めて目標を決めます。\n\n測定前のSLO達成宣言や、予算通知だけで費用が止まるという判断は避けます。運用・復旧・コストを同じ改善サイクルへ戻します。"),
        ], phase_diagram(8))

    add(9, "comparison", "ECSとEKSを選び分ける", "予習 / 要件から採用判断へ", "review", 40,
        "EKS採用を正解にせず、同じ要件と根拠で選択肢を比べます。", [
            concept("比較条件", "規模・チーム・可用性・移植性などをそろえて比較します。", "同じ荷物と距離で運送方法を選ぶ"),
            concept("運用負荷", "導入後に更新・障害対応・監視を続けるための負担です。", "購入費とは別に必要な維持費と手間"),
            concept("不確実性", "未測定・未確定の前提を明示し、追加調査へつなげます。", "見積もりの根拠と未確定欄"),
        ], [
            section("scenario", "同じサービス要件で比較する", "設計書の仮定は、月間数十万リクエスト規模の社内タスク管理を少人数で運用し、将来複数サービスが加わる可能性がある状況です。これはユーザーの実要件ではなく、比較のための課題シナリオです。\n\n初期構築、運用責任、スケール、可用性、セキュリティ、コスト、開発体験、長期戦略を比べます。"),
            section("decision", "採用案を反対案と一緒に書く", "採用案だけでなく、もう一方を選ばない理由と、その判断が変わる条件も残します。既存技術や組織の習熟度も要件の一部です。\n\n料金の定量比較はregion・時間・構成・調査日をそろえて公式情報を確認する必要があります。この予習教材では現行料金を断定していません。"),
        ], phase_diagram(9))


ICON_DIR = Path(__file__).resolve().parents[1] / "public" / "icons"


def validate_diagram(diagram):
    nodes = diagram["nodes"]
    assert 4 <= len(nodes) <= 20
    node_ids = {node["id"] for node in nodes}
    assert len(node_ids) == len(nodes)
    group_ids = {group["id"] for group in diagram["groups"]}
    assert len(group_ids) == len(diagram["groups"])
    assert all(e["from"] in node_ids and e["to"] in node_ids for e in diagram["edges"])
    assert all(group["parentId"] in group_ids for group in diagram["groups"] if "parentId" in group)
    for node in nodes:
        assert node.get("resource"), node["id"]
        assert "group" not in node or node["group"] in group_ids, node["id"]
        vendor, _, name = node["resource"].partition(".")
        if vendor in ("kubernetes", "aws"):
            assert (ICON_DIR / vendor / f"{name}.svg").is_file(), node["resource"]
    for view in diagram["views"]:
        assert view["nodeIds"] and set(view["nodeIds"]) <= node_ids, view["id"]


def validate(phases):
    assert [phase["id"] for phase in phases] == list(range(10))
    for phase in phases:
        assert phase["implemented"] == (phase["id"] < 3)
        assert phase["goals"] and phase["questions"] and phase["memoFields"]
        assert all(q["prompt"] and q["rubric"] for q in phase["questions"])
        assert all((ROOT / source["path"]).is_file() for source in phase["sources"])
        validate_diagram(phase["diagram"])
        if phase["id"] >= 3:
            assert not any(s.get("steps") for s in phase["sections"])
        else:
            practice = [s for s in phase["sections"] if s.get("kind") == "practice"]
            assert practice and any(s.get("steps") for s in practice)
            assert len({s["id"] for s in phase["sections"]}) == len(phase["sections"])
            assert all(not any(word in s["title"] for word in ("学習メモ", "回答", "実装時")) for s in practice)


if __name__ == "__main__":
    output = Path(__file__).with_name("curriculum.json")
    output.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("教材を生成しました: Phase 0〜9 / 既存ラボは読み取りのみ")
