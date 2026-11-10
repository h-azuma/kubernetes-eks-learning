"""既存の設計書・ラボを読み取り、ポータル用教材を再生成する。"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = "docs/kubernetes-eks-hands-on-design.md"
LABS = [
    "phases/00-foundation/README.md",
    "phases/01-compose/README.md",
    "phases/02-kind-basics/README.md",
    "phases/03-config-storage/README.md",
    "phases/04-reliability-scaling/README.md",
    "phases/05-security-and-failure/README.md",
    "phases/06-eks-foundation/README.md",
    "phases/07-aws-integration/README.md",
    "phases/08-devops-observability/README.md",
    "phases/09-architecture-review/README.md",
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
    return [label.strip() for label in re.findall(r"^- (.+)$", heading_body(text, "学習メモ"), re.M)]


SHELL_LABEL = re.compile(r"^\*\*(?:Windows \(PowerShell\)|Linux / macOS / WSL \(Bash\)):\*\*[ \t]*$", re.M)


def plain_text(markdown):
    """手順説明の装飾だけを除き、URLと安全条件を残す。シェル切替の見出しは画面のタブで示す。"""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", SHELL_LABEL.sub("", markdown))
    return text.replace("**", "").strip()


PURPOSE, CHECK = "目的：", "確認："
PRACTICE_HEADINGS = ["前提条件", "検証コマンド・期待結果", "検証方法・期待結果", "故障実験", "失敗時に確認すること", "Linux / macOS / WSL での前提", "後片付け"]


def paragraphs(markdown):
    return [text for text in re.split(r"\n\s*\n", plain_text(markdown)) if text]


def practice_sections(text, prefix, allowed_headings):
    """指定した手順節だけを抽出する。回答・メモ・検証記録は対象外。

    コマンド（PowerShell/Bash の対は1つ）ごとに、直前の「目的：」段落を description、直後から次の
    「目的：」までの段落を expected にする。どちらかが無ければ ValueError。最初の手順より前の
    「目的：」以外の段落は節の本文、手順間にある「確認：」以外の段落は直前手順の expected に含める。
    """
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
            (subheading, (introduction + "\n\n" if number == 0 else "") + subcontent)
            for number, (subheading, subcontent) in enumerate(zip(parts[1::2], parts[2::2]))
        ]
        for subheading, subcontent in subsections:
            blocks = list(re.finditer(r"```([^\n]*)\n(.*?)```", subcontent, re.S))
            units = []
            index = 0
            while index < len(blocks):
                block = blocks[index]
                following = blocks[index + 1] if index + 1 < len(blocks) else None
                is_pair = (
                    block.group(1).strip() == "powershell" and following is not None
                    and following.group(1).strip() == "bash"
                    and not plain_text(subcontent[block.end():following.start()])
                )
                units.append((block, following if is_pair else None))
                index += 2 if is_pair else 1
            starts = [0] + [(pair or block).end() for block, pair in units]
            ends = [block.start() for block, _ in units] + [len(subcontent)]
            gaps = [paragraphs(subcontent[start:end]) for start, end in zip(starts, ends)]
            body = gaps[0][:-1] if units else gaps[0]
            steps = []
            for number, (block, pair) in enumerate(units):
                where = f"{subheading} 手順 {number + 1}"
                if not gaps[number] or not gaps[number][-1].startswith(PURPOSE):
                    raise ValueError(f"{where}: 直前に「{PURPOSE}」の段落がありません")
                after = gaps[number + 1] if number + 1 == len(units) else gaps[number + 1][:-1]
                if not any(text.startswith(CHECK) for text in after):
                    raise ValueError(f"{where}: 直後に「{CHECK}」の段落がありません")
                label = "Windows / Linux" if pair else {"powershell": "PowerShell", "bash": "Bash", "text": "共通コマンド"}.get(block.group(1).strip(), "コマンド")
                item = dict(
                    title=f"手順 {number + 1} / {label}",
                    description=gaps[number][-1].removeprefix(PURPOSE),
                    command=block.group(2).strip(),
                    expected="\n\n".join(text.removeprefix(CHECK) for text in after),
                )
                if pair:
                    item["linuxCommand"] = pair.group(2).strip()
                elif block.group(1).strip() in ("powershell", "bash"):
                    item["shell"] = block.group(1).strip()
                steps.append(item)
            body = "\n\n".join(body)
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


def section(key, title, body, callout=None):
    result = {"id": key, "title": title, "body": body}
    if callout:
        result["callout"] = callout
    return result


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
        nodes = [pod("api-pod", "API Pod", "FastAPI", 0), diagram_node("db-service", "DB Service", "kubernetes.service", "安定した論理接続先", "namespace", 1), pod("db-pod", "DB Pod", "PostgreSQL", 1), diagram_node("sts", "DB StatefulSet", "kubernetes.statefulset", "Pod の識別子と保存先の対応", "management", 1), diagram_node("pvc", "PVC", "kubernetes.pvc", "Pod 専用の保存先要求", "namespace", 2), diagram_node("pv", "PV", "kubernetes.pv", "cluster scope の保存領域オブジェクト", "cluster", 2), diagram_node("config", "ConfigMap", "kubernetes.configmap", "非機密の設定値（ハッシュ付き名）", "namespace", 0), diagram_node("secret", "Secret", "kubernetes.secret", "base64 表現。権限・保存時保護は別途必要", "namespace", 1)]
        edges = [relation("api-pod", "db-service", "SQL"), relation("db-service", "db-pod", "SQL / selector"), relation("sts", "db-pod", "所有 / 安定した識別子", "ownership"), relation("db-pod", "pvc", "mount に使用", "storage"), relation("pvc", "pv", "バインド", "storage"), relation("config", "api-pod", "設定を注入", "configuration"), relation("secret", "api-pod", "接続情報を配布", "configuration"), relation("secret", "db-pod", "接続情報を配布", "configuration")]
        views = [diagram_view("storage", "保存先とスコープ", "workboard-phase3 の DB 周辺図です。StatefulSet は ReplicaSet を介しません。PVC は Namespace 内、PV と Node は cluster scope です。PV は物理ディスクそのものの絵ではありません。", ["api-pod", "db-service", "db-pod", "sts", "pvc", "pv"], ["traffic", "ownership", "storage"]), diagram_view("configuration", "設定の配布", "ConfigMap/Secret は実行中のコンテナではなく、API に保存される設定オブジェクトです。内容が変わると名前のハッシュが変わり、参照する Pod は置き換わります。", ["config", "secret", "api-pod", "db-pod"], ["configuration"])]
        return diagram_model("storage", "Pod の寿命と保存先を分離する", "Phase 3 の構成です。Web や管理チェーンなど、今回の焦点以外は省略しています。Node と Namespace は直交します。PV は kind のノード内の保存領域で、ノード喪失を含めた可用性の保証ではありません。", nodes, edges, k8s_groups(), views, dict(api=["api-pod"], database=["db-pod", "pvc", "pv"], migration=[]))
    if phase_id == 4:
        groups = k8s_groups("Node A / 実行場所") + [diagram_group("node-b", "Node B / 実行場所", "node", "cluster")]
        nodes = [diagram_node("metrics", "CPU 指標", "document", "metrics-server 等から得る値", "cluster", 0), diagram_node("hpa", "HPA", "kubernetes.hpa", "replicas を調整する宣言", "management", 0), diagram_node("deploy", "API Deployment", "kubernetes.deployment", "更新方針と必要数", "management", 1), diagram_node("rs", "API ReplicaSet", "kubernetes.replicaset", "Pod 数を維持", "management", 1), diagram_node("service", "API Service", "kubernetes.service", "準備できた Pod を選択", "namespace", 0), pod("api-a", "API Pod A", "FastAPI", 0), pod("api-b", "API Pod B", "FastAPI", 0, "node-b")]
        edges = [relation("metrics", "hpa", "判断材料", "configuration"), relation("hpa", "deploy", "replicas を調整", "control"), relation("deploy", "rs", "所有", "ownership"), relation("rs", "api-a", "所有", "ownership"), relation("rs", "api-b", "所有", "ownership"), relation("service", "api-a", "HTTP"), relation("service", "api-b", "HTTP")]
        views = [diagram_view("traffic", "通信と配置", "API の拡大図です。Service は Node 内のプロセスではありません。Pod を異なる Node に置くのは topologySpreadConstraints の条件で、レプリカ数だけでは決まりません。", ["service", "api-a", "api-b"], ["traffic"]), diagram_view("control", "数を調整する関係", "指標→HPA→Deployment は制御。Deployment→ReplicaSet→Pod は所有関係です。HPA は Node 台数を直接増やしません。", ["metrics", "hpa", "deploy", "rs", "api-a", "api-b"], ["configuration", "control", "ownership"])]
        return diagram_model("scaling", "通信・レプリカ制御・Node 配置", "workboard-phase4（control-plane 1 + worker 2）の API 部分の拡大図です。DB/Web は省略しています。", nodes, edges, groups, views)
    if phase_id == 5:
        nodes = [diagram_node("user", "利用者", "identity", "Kubernetes API を操作する主体", "host"), diagram_node("sa", "ServiceAccount", "kubernetes.serviceaccount", "ワークロードの API アクセス主体", "namespace", 0), diagram_node("role", "Role / RoleBinding", "kubernetes.role", "Namespace 内の認可設定", "management", 1), diagram_node("kapi", "Kubernetes API", "kubernetes.api", "Control Plane の API", "cluster", 2), pod("web-pod", "Web Pod", "Nginx", 0), diagram_node("api-service", "API Service", "kubernetes.service", "HTTP の接続先", "namespace", 1), pod("api-pod", "API Pod", "FastAPI", 1), diagram_node("policy", "NetworkPolicy", "kubernetes.networkpolicy", "対応 CNI が適用する通信規則", "namespace", 2)]
        edges = [relation("user", "kapi", "API 操作要求", "control"), relation("sa", "kapi", "Pod の API 要求", "control"), relation("role", "kapi", "認可条件", "configuration"), relation("web-pod", "api-service", "HTTP"), relation("api-service", "api-pod", "HTTP"), relation("policy", "api-pod", "許可・拒否の設定", "configuration")]
        views = [diagram_view("authorization", "操作する権限", "RBAC は API に何を要求できるかを決めます。ServiceAccount はコンテナではありません。", ["user", "sa", "role", "kapi"], ["configuration", "control"]), diagram_view("network", "アプリの通信", "実線が HTTP。NetworkPolicy 自体が通信を中継するのではなく、対応 CNI がルールを適用します。", ["web-pod", "api-service", "api-pod", "policy"], ["traffic", "configuration"])]
        return diagram_model("security", "API 権限とアプリ通信を分ける", "workboard-phase5（Calico）の構成です。Namespace の権限と Pod の実行場所を区別して描きます。", nodes, edges, k8s_groups(), views)
    if phase_id == 6:
        groups = [diagram_group("outside", "構成を定義する利用者", "external"), diagram_group("aws", "AWS 環境 / 責任の分担", "aws"), diagram_group("cluster", "EKS / Kubernetes クラスター", "cluster", "aws"), diagram_group("managed-control", "AWS が運用する Control Plane", "aws", "cluster"), diagram_group("runtime", "Managed Node Group / EC2 上の Node", "node", "cluster")]
        nodes = [diagram_node("tf", "Terraform", "document", "利用者が構成と差分を管理", "outside", 0), diagram_node("vpc", "VPC / subnet", "aws.vpc", "利用者が経路・アクセス範囲を設計", "aws", 0), diagram_node("eks", "EKS Control Plane", "aws.eks", "AWS が運用・利用者がアクセス設定", "managed-control", 1), diagram_node("ecr", "ECR", "aws.ecr", "クラスター外のイメージ保管", "aws", 2), pod("web-pod", "Web Pod", "Nginx", 0), pod("api-pod", "API Pod", "FastAPI", 1)]
        edges = [relation("tf", "vpc", "構成を定義", "configuration"), relation("tf", "eks", "構成を定義", "configuration"), relation("eks", "web-pod", "配置・状態の調整", "control"), relation("eks", "api-pod", "配置・状態の調整", "control"), relation("ecr", "web-pod", "イメージを配布", "configuration"), relation("ecr", "api-pod", "イメージを配布", "configuration")]
        return diagram_model("eks", "AWS 管理と利用者の責任", "Phase 6 の構成（AWS 上は未検証）。標準 EKS の Control Plane は AWS が運用します。Managed Node Group でも Node/AMI 更新方針・アドオン・アプリ設定は利用者の責任として残ります。枠は実行配置と責任の説明で、VPC が Control Plane 全体を包含するという意味ではありません。", nodes, edges, groups)
    if phase_id == 7:
        groups = k8s_groups("EKS の Node / 利用者のワークロード")
        groups.insert(1, diagram_group("aws", "AWS マネージドサービス", "aws"))
        next(group for group in groups if group["id"] == "cluster")["parentId"] = "aws"
        nodes = [diagram_node("browser", "ブラウザー", "browser", "制限した検証アクセス", "host", 0), diagram_node("alb", "ALB", "aws.alb", "クラスター外の HTTP 入口", "aws", 0), diagram_node("rds", "RDS PostgreSQL", "aws.rds", "クラスター外の DB", "aws", 2), diagram_node("iam", "IAM role", "aws.iam", "Controller の ALB 管理権限", "aws", 3), diagram_node("ingress", "Ingress 定義", "document", "Kubernetes API に保存する入口の宣言", "management", 0), diagram_node("web-service", "Web Service", "kubernetes.service", "ターゲットを選ぶ backend 定義", "namespace", 0), diagram_node("api-service", "API Service", "kubernetes.service", "内部 HTTP 接続先", "namespace", 1), pod("web-pod", "Web Pod", "Nginx", 0), pod("api-pod", "API Pod", "FastAPI", 1), pod("lbc-pod", "Controller Pod", "AWS Load Balancer Controller", 3)]
        nodes[-5]["namespace"] = "workboard"  # Ingress も namespaced な API オブジェクト。
        edges = [relation("browser", "alb", "HTTP / 制限付き"), relation("alb", "web-pod", "HTTP / IP ターゲット案"), relation("web-pod", "api-service", "/api/ HTTP"), relation("api-service", "api-pod", "HTTP"), relation("api-pod", "rds", "SQL"), relation("web-service", "web-pod", "selector", "configuration"), relation("ingress", "web-service", "backend を宣言", "configuration"), relation("ingress", "lbc-pod", "監視する定義", "configuration"), relation("lbc-pod", "alb", "作成・更新を要求", "control"), relation("iam", "lbc-pod", "AWS API 権限", "configuration")]
        views = [diagram_view("traffic", "HTTP と SQL の経路", "IP ターゲット方式です。ALB は選ばれた Web Pod へ直接転送します。Service はターゲット選択の論理設定で、Controller はリクエストを中継しません。", ["browser", "alb", "web-service", "web-pod", "api-service", "api-pod", "rds"], ["traffic", "configuration"]), diagram_view("control", "ALB を管理する関係", "Ingress は宣言、Controller Pod は実行中のプログラム、ALB は AWS の別サービスです。Controller はクラスター外の ALB を管理できるため、実行場所と管理対象の境界は一致しません。", ["ingress", "web-service", "lbc-pod", "alb", "iam"], ["control", "configuration"])]
        return diagram_model("integration", "Kubernetes と AWS サービスの連携", "Phase 7 の構成（AWS 上は未検証）。RDS/ALB/IAM は Kubernetes Pod ではありません。IAM 図は Controller の AWS API 操作権限で、アプリの RDS SQL 認証とは別です。", nodes, edges, groups, views)
    if phase_id == 8:
        nodes = [diagram_node("git", "Git の変更", "document", "構成の正本", column=0), diagram_node("ci", "CI", "pipeline", "テスト・ビルド", column=1), diagram_node("approve", "承認", "document", "反映するかの判断", column=2), diagram_node("cd", "CD / GitOps", "pipeline", "方式を比較して選ぶ", column=3), diagram_node("app", "対象環境", "document", "構成と実状態の照合先", column=4), diagram_node("observe", "ログ・指標", "document", "SLI と復旧判断", column=5)]
        edges = [relation("git", "ci", "検査", "configuration"), relation("ci", "approve", "結果", "configuration"), relation("approve", "cd", "反映を許可", "control"), relation("cd", "app", "更新", "control"), relation("app", "observe", "計測結果", "configuration"), relation("observe", "git", "改善", "configuration")]
        return diagram_model("pipeline", "変更から次の改善へ", "Phase 8 の工程です。これは工程と情報の流れで、箱がすべて Kubernetes リソースやコンテナという意味ではありません。", nodes, edges)
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
    [
        ["安定した識別子とストレージを扱うStatefulSetの用途を説明する", "StatefulSetだけでバックアップやDBの高可用性は完成しないと説明する"],
        ["Podの寿命から保存先を分離すると説明する", "PVC削除やreclaim policy、ノード喪失・誤削除・バックアップの課題を区別する"],
        ["overlayはbaseのYAMLへのパッチで環境差分を表すと説明する", "変数展開や条件分岐を行うテンプレートエンジンではなく、存在しないリソースを自動では作らないと説明する"],
        ["Secretはbase64で表現されるだけで暗号化ではないと説明する", "読み取りやexecができる主体、RBAC、保存時の保護、配布先を含めて考える"],
        ["ConfigMap/Secretの内容変更でハッシュ付き名が変わりPodテンプレートが更新されると説明する", "環境変数は起動時に決まるため、既存Podは自動で新しい値に変わらないと区別する"],
    ],
    [
        ["同一ノードに載ったレプリカがノード障害で同時に止まり得ると説明する", "2 ノードでも残る単一障害点（1 Pod の DB、port-forward、同一ホスト）を挙げる"],
        ["上限は maxReplicas・指標・requests・ノードの空きで決まり、ノード台数とは直結しないと説明する", "置けない Pod は Pending になり、ノード追加は別の仕組みだと説明する"],
        ["Liveness を DB 非依存にする理由として再起動の連鎖を説明する", "Startup と Readiness の役割と、DB 停止時に各 Probe が何を起こすかを区別する"],
        ["requests の根拠（実測など）と、HPA の使用率の分母が requests であることに触れる", "CPU は throttling、memory は OOMKill という超過時の違いを区別する"],
        ["drain など自発的な退避だけが対象と説明する", "ノード故障・直接削除・単一レプリカの DB では守れないことを区別する"],
        ["maxSurge / maxUnavailable と容量・可用性のトレードオフを説明する", "undo で戻るもの（Pod テンプレート）と戻らないもの（DB のデータなど）を区別する"],
        ["DoNotSchedule は Pending、ScheduleAnyway は偏りを許すという違いを説明する", "可用性要件に応じた選択の理由か、taint のあるノードの扱いに触れる"],
    ],
    [
        ["Secret は base64 で暗号化ではなく、読める主体・exec できる主体は値を得られると説明する", "保存時暗号化・RBAC・監査など別の対策の範囲に触れる"],
        ["人・アプリの Pod・調査ツールで必要な権限を分け、最小権限で説明する", "不要な Pod に ServiceAccount トークンを自動マウントしない理由を述べる"],
        ["TUI の操作範囲はツールではなく資格情報に対する RBAC で決まると説明する", "読み取り専用の主体や運用で編集・削除を避ける理由に触れる"],
        ["enforce は Pod を拒否し、warn・audit は警告・記録であることを区別する", "restricted を enforce にできる条件と、バージョン固定の意義に触れる"],
        ["防げること（権限昇格・書き込み・不要な capability）と防げないこと（Secret の閲覧、アプリの脆弱性）を区別する", "イメージ変更とマニフェストで補う方式の判断基準（他 Phase への影響など）を述べる"],
        ["遮断するのは CNI で、対応しない CNI では効かないと説明する", "許可と拒否の両方を実測で確かめ、タイムアウトと refused を見分けると述べる"],
        ["名前解決・EndpointSlice・ポート・NetworkPolicy の順に切り分ける手順を示す", "kubelet の Probe は NetworkPolicy の影響を受けず、Ready のまま遮断され得ると説明する"],
    ],
    [
        ["AMI 更新・パッチ・台数・脆弱性対応が利用者に残ると説明する", "EKS が担う範囲（Control Plane、作成やドレイン付き更新の支援）と区別する"],
        ["Auto Mode ではノードやアドオンの管理も AWS 側に寄ると説明する", "見えなくなる運用と、増える費用・制約に触れる"],
        ["料金・遅延・AZ 数・サービスの有無など複数の観点を挙げる", "選んだ region で料金を確認する必要を述べる"],
        ["public を CIDR で制限するか private にするかの判断を示す", "kubectl・Terraform の経路と、IP が変わったときの影響に触れる"],
        ["NAT の時間料金・データ処理料金と AZ 障害時の影響のトレードオフを述べる", "学習用途としての判断根拠を示す"],
        ["ノードを private subnet に置く理由（直接の露出を避ける）を述べる", "ALB は public、ノードと DB は private という役割分担を説明する"],
        ["ローカルと remote の選択肢と、機密を含むため Git に入れない点を述べる", "state を失うと destroy できなくなるリスクに触れる"],
    ],
    [
        ["パッチ・バックアップ・フェイルオーバーの運用責任が AWS に移ると説明する", "費用・AWS 依存・ネットワーク設計という増えるものにも触れる"],
        ["/health/ready が 503 になり Service の宛先から外れると説明する", "ALB の health check を / にするか /health/ready にするかの影響を比較する"],
        ["生成物（RBAC・Webhook・Deployment・CRD・Secret）を helm template で読むと述べる", "出典・版・values の固定、IAM 権限、Webhook の failurePolicy のいずれかに触れる"],
        ["private subnet とセキュリティグループ参照（ノード側からの 5432 のみ）を述べる", "VPC 全体や 0.0.0.0/0 に開けない理由を述べる"],
        ["Secrets Manager で管理し、state や Git に平文を残さない点を述べる", "ローテーション時の追従（再取得・Pod の再作成）に触れる"],
        ["Pod Identity で ServiceAccount 単位に IAM ロールを渡すと説明する", "ノードのロールに付ける方式と最小権限の観点で比較する"],
        ["inbound-cidrs による許可 IP の制限と、短時間の検証用途に限ることを述べる", "Ingress を先に削除して ALB を消す順序と理由を述べる"],
        ["pg_dump / pg_restore による論理移行を VPC 内の経路で行うと述べる", "自動バックアップ・PITR・スナップショットの違いと、復元は新しいインスタンスになる点に触れる"],
    ],
    [
        ["GitOps は Git を正本に継続的に差分を調整する pull 型、CI からの apply は push 型と区別する", "認証情報の置き場所・drift の扱い・対象が増えたときの有利不利を比較する"],
        ["Helm は配布・パッケージ化・release 管理、Kustomize は自分の YAML の環境差分に向くと説明する", "併用すると生成が二段になり出所と差分を追いにくくなることと、判断の基準を述べる"],
        ["Git に置けない値の扱い方（事前作成、Sealed Secrets、External Secrets など）を挙げる", "選んだ方式で残る課題（手作業、ローテーション、鍵の管理など）を述べる"],
        ["SLI の分子・分母・除外条件（ヘルスチェックなど）と期間を明示する", "測定前に達成と断言せず、目標値の根拠を述べる"],
        ["承認を本番反映の直前に置き、承認者が確認する内容（差分、テスト結果、対象）を述べる", "OIDC の信頼条件をリポジトリ・ブランチ・environment で絞ると説明する"],
        ["リクエスト率・エラー率・p95 など、どの指標で何が分かるかを説明する", "メトリクスで分からないとき（Nginx の 504/502 など）に使うログ・イベントを挙げる"],
        ["予算通知・Cost Explorer による確認と、削除の手順・タグによる点検を組み合わせる", "予算通知は課金停止を保証しないなど、防げないことを述べる"],
    ],
    [
        ["ECS と EKS で必要な構成要素を実際に挙げて比べる", "要件の実現に必要な最小構成と、学習済みの経験を区別する"],
        ["起動タイプ・ノード管理方式ごとに OS・パッチ・容量・アドオンの担当を区別する", "EKS でもノード運用の責任が残り得る点を方式別に説明する"],
        ["Task/Pod の増減と Node/容量の増減の関係を両案で説明する", "追従が遅れる条件に触れる"],
        ["ノード・AZ・DB の障害を分けて対応を書く", "RDS の障害の影響は両案で共通であることを踏まえる"],
        ["IAM（タスクロール / Pod Identity）・ネットワーク・コンテナ権限・監査を比べる", "実行基盤の権限とアプリの権限を区別する"],
        ["region・時間・構成・調査日をそろえた見積もり条件を記録する", "運用人件費と移行費用を仮定を明示して含める"],
        ["GitOps・共通基盤・エコシステムとチームの学習負荷を両案で比べる", "自分の Phase 8 の観察を根拠にし、未観察ならそう書く"],
        ["将来のサービス追加・移植性・既存技術が結論に与える影響を条件付きで書く", "どちらも無条件の正解とせず、判断が変わる条件を示す"],
    ],
]


def build():
    lab_texts = [read(path) for path in LABS]
    phases = []

    def add(pid, slug, title, subtitle, level, minutes, summary, concepts, sections, graph):
        text = lab_texts[pid]
        goals = re.findall(r"^- (.+)$", heading_body(text, "学習目標"), re.M)
        prompts = lab_questions(text)
        labels = memo_labels(text)
        rubrics = RUBRICS[pid]
        if pid == 1:
            sections.extend(practice_sections(
                text, "practice-setup",
                ["Phase 1: Compose 上で WorkBoard を起動する"],
            ))
        sections.extend(practice_sections(text, "practice-lab", PRACTICE_HEADINGS))
        assert len(prompts) == len(rubrics), (pid, prompts)
        phases.append(dict(
            id=pid, slug=slug, title=title, subtitle=subtitle, level=level,
            implemented=True, estimatedMinutes=minutes, summary=summary,
            goals=goals, concepts=concepts, sections=sections, diagram=graph,
            questions=[dict(id=f"q{i}", prompt=prompt, rubric=rubric) for i, (prompt, rubric) in enumerate(zip(prompts, rubrics), 1)],
            memoFields=[dict(id=f"m{i}", label=label) for i, label in enumerate(labels, 1)],
            sources=[dict(label="一次設計書", path=DESIGN), dict(label=f"Lab {pid:02d} 原本", path=LABS[pid])],
        ))

    add(0, "foundation", "学習の土台を整える", "環境確認と設計判断の記録", "foundation", 25,
        "何が使えるかを確かめ、事実と未検証を分けて記録します。", [
            concept("preflight", "後の作業に必要なツールを参照のみで確認する準備点検です。", "出発前に道具をそろえる点検表"),
            concept("ADR", "採用した案・代替案・理由・影響を残す短い設計記録です。", "後から判断をたどれる議事録"),
            concept("一次設計書", "方針の原本を一か所で管理し、入口の文書から参照します。", "地図の正本と案内板"),
        ], [
            section("start", "二つの画面を使い分ける", "このポータルは学習・回答用の localhost:8765、WorkBoardはタスク操作用の localhost:8080 です。ポータルを開いてもWorkBoardやkindを起動・停止しません。\n\n各章で解説と図を読み、実際の観察は学習メモへ、設計判断は設計課題へ書きます。採点への送信では、何を実行し何を省略したかも伝えてください。"),
            section("check", "導入済みと稼働中は別", "バージョンが返ればCLIの実行は確認できます。Dockerエンジンの起動、DB接続、WSL連携や互換性まで確認できたとは限りません。\n\n→ 実習「検証コマンド・期待結果」で確かめます。"),
            section("record", "履歴と秘密情報を分ける", ".gitignoreは新たな追跡を避けるための設定です。追跡済みの秘密情報や過去の履歴は消しません。\n\n学習メモには観察・コマンド・期待との差を書きます。設計課題には自分の理由と代替案を書き、結果だけの『できた』から一歩進めます。", "補助解説はポータル独自の編集です。設計課題と学習メモの項目名は既存ラボを正本にしています。"),
        ], phase_diagram(0))

    add(1, "compose", "3層アプリを動かす", "Docker Compose とデータの寿命", "foundation", 45,
        "Web・API・DBの通信と、起動・準備完了・永続化の違いをつかみます。", [
            concept("コンテナとlocalhost", "コンテナごとにプロセスとネットワークの境界があります。API内のlocalhostはAPI自身です。", "別々の部屋で『この部屋』と呼ぶ感覚"),
            concept("Readiness", "リクエストを受け付けられるかを確認します。プロセス生存とは別の条件です。", "開店していることと注文に応えられることの違い"),
            concept("named volume", "DBコンテナを取り替えても残せる保存先です。volume自体を削除すれば保存データは失われます。", "部屋を引っ越しても持っていける収納箱"),
        ], [
            section("flow", "入口はWebだけ", "ブラウザーは8080番のNginxへ接続します。静的画面を受け取り、/api/の呼び出しはNginxがAPIへ転送します。APIはDBサービス名でPostgreSQLへ接続します。\n\nAPI/DBのポートをホストに公開しなくても、同じComposeネットワーク内では通信できます。コンテナを分ける主な理由は個別の更新・再起動・管理です。分割だけで冗長化が完成するわけではありません。\n\n→ 実習「1. 設定と起動を確認する」「3. API と health を確認する」で確かめます。"),
            section("startup", "起動順と準備完了は別", "DB→migration→API→Webの順に準備します。service_healthyはDBの準備条件、service_completed_successfullyはmigrationの正常終了を待つ条件です。\n\nこれは起動時の条件です。稼働中のDB障害では接続の回復やエラー処理が別途必要になります。migrationはテーブルを用意する一回の処理で、長時間リクエストを受けるAPIとは役割が異なります。\n\n→ 実習「1. 設定と起動を確認する」で確かめます。", "現在kindを使用して8080を転送中なら、そのまま学習できます。Composeを重ねて起動せず、初回構築はこの章の実習を開いて進めてください。"),
            section("health", "Liveness・Readiness と保存先", "LivenessはAPIの生存、ReadinessはDBへの接続を確認します。DB停止時にliveまで失敗させると、APIを再起動してもDB障害は直らず、再起動が連鎖し得ます。\n\nAPIやブラウザーを再起動してもタスクが残るのは、DBがnamed volumeに保存するためです。現在8080がkindを向いていれば、同じURLでも保存先はkindのDBです。異なる環境のデータを同じものと考えないでください。\n\n→ 実習「3. API と health を確認する」「4. 再起動・公開ポート・データ保持を観察する」で確かめます。"),
        ], phase_diagram(1))

    add(2, "kubernetes", "望ましい状態を保つ", "kind・Pod・Service・一時DB", "local", 60,
        "Podが置き換わっても通信できる理由と、データまで復旧するとは限らない理由を学びます。", [
            concept("Podとコンテナ", "PodはKubernetesの配置・実行の単位です。一つ以上のコンテナがネットワークとvolumeを共有します。", "同じ住所と共有設備を持つ作業室"),
            concept("Deployment", "ReplicaSetを通して指定数のPodを維持し、更新を管理します。Podが失われると別のPodを作ります。", "必要人数を補充する現場の管理者"),
            concept("ClusterIP Service", "selectorでPodを選び、クラスター内に安定した接続先を用意します。", "担当者が替わっても使える代表窓口"),
            concept("emptyDir", "Podに属する一時volumeです。コンテナの再起動を越えて残っても、Pod削除では消えます。", "同じ作業室の中だけで使える棚"),
            concept("JobとinitContainer", "Jobは完了を目指す一回の処理です。通常のinitContainerは同じPodの主コンテナより前に正常終了する必要があります。", "独立した準備作業と、開店前の室内準備の違い"),
        ], [
            section("observe", "kind の Node・Pod・Deployment の階層", "この環境のPhase 2は構築済みです。読み取りコマンドからPod・ReplicaSet・Deployment・Serviceを見比べます。各コマンドは専用contextを明示し、別クラスターと混同しないようにします。\n\nkindのNodeもローカルDocker内で動きます。Nodeの中にPod、その中にコンテナという階層です。アプリのコンテナイメージはComposeと共通でも、起動・維持する主体が変わります。\n\n→ 実習「2. 現在のシェルで対象を選び、状態を観察する」で確かめます。", "以下は手動実行用です。ポータルはコマンドを自動実行しません。既存Podの削除や再構築はここでは必要ありません。"),
            section("network", "Serviceとport-forwardを分ける", "Web→APIの通信はClusterIP Serviceを利用します。ServiceのselectorとPodのlabelが一致しないと、期待するPodへ転送されません。PodがRunningであることだけでは通信の成功を保証しません。\n\nsvc/workboard-webを指定したport-forwardはselectorで選んだWeb Podへの一時トンネルです。ClusterIPそのものを外部公開する操作ではありません。WorkBoardはlocalhost:8080、学習ポータルはlocalhost:8765です。既存の転送を止めず、そのまま8080を利用できます。\n\n→ 実習「3. ブラウザーで同じアプリを使う」で確かめます。", "port-forwardは常設の公開設定ではありません。接続しているWeb Podの置き換えでも終了する場合があります。"),
            section("lifecycle", "再作成はデータ復元ではない", "API Podを削除するとDeploymentが新しいPodを補います。DB PodとそのemptyDirが残るのでタスクは保持されます。PodのUIDは変わりますが、IPは再利用される場合もあります。\n\nDB Podを削除すると、新しいemptyDirでDBが立ち上がります。タスクだけでなくスキーマも失われます。完了済みmigration JobはDB再作成だけでは再実行されません。Jobを再実行してスキーマを作り直しても、元データの復元にはなりません。\n\n→ 実習「4. API Pod を削除し、自動復旧を観察する」「故障実験: 一時 DB とデータ消失」で確かめます。", "DB削除実験はデータ消失を伴います。実行する場合はLab 02の条件・対象を確認し、失ってよいと判断してから別途行ってください。"),
            section("init", "initContainerで解ける範囲", "現在のPhase 2はmigration Jobを使っており、API PodにinitContainerはありません。比較として、initContainerは同じPodの主コンテナより前に順番に実行され、準備を終えてから主コンテナを起動できます。\n\nAPI PodのinitContainerでDBを準備したとしても、別のDB Podだけが再作成されたとき、既存API PodのinitContainerは自動で再実行されません。DB障害中の接続回復やmigrationの再実行方針は、別に設計する必要があります。\n\n/health/readyのSELECT 1はDB接続を確かめます。テーブルの存在やmigration完了まで調べるものではないので、readyが200でもCRUDが失敗する場面があります。"),
        ], phase_diagram(2))

    add(3, "storage", "設定とデータを切り離す", "kind・Kustomize・StatefulSet・PVC", "local", 70,
        "設定・Secret・保存先をPodの寿命から切り離し、守れる範囲と守れない範囲を観察します。", [
            concept("Kustomize", "baseに共通のYAML、overlayに環境差分を置き、パッチとgeneratorで最終的なYAMLを組み立てます。変数展開を行うテンプレートエンジンではありません。", "原本の図面に環境別の修正指示を重ねる"),
            concept("PVC / PV", "アプリの保存先要求と、それに応える保存領域を分けます。PVCはNamespace内、PVはクラスター全体のオブジェクトです。", "倉庫の利用申込書と割り当てられた棚"),
            concept("StatefulSet", "Podの名前と専用のPVCの対応を保つ仕組みです。バックアップやDBの高可用性までは扱いません。", "名前付きの担当席と専用保管庫"),
            concept("ConfigMap / Secret", "設定と秘密情報をイメージから分離します。Secretはbase64表現で暗号化ではなく、権限設計が必要です。", "共有手順書と配布先を絞った鍵"),
        ], [
            section("kustomize", "Kustomize の base と overlay", "新しい専用クラスター workboard-phase3 で行います。Phase 2 の workboard-lab は変更しません。\n\nbaseにはNamespaceもConfigMap/Secretもありません。overlayがnamespace・イメージ・imagePullPolicyを変え、ConfigMapとSecretを生成します。生成された名前にはハッシュが付き、参照側の名前も書き換わります。\n\n→ 実習「1. 適用前に生成結果を読む」で確かめます。", "kubectl kustomize は生成結果を表示するだけで、クラスターを変更しません。Secret の入力は Git 管理外の db.env です。"),
            section("persistence", "Podの寿命を越える保存先", "StatefulSetのPodは固定名で、volumeClaimTemplatesからPod専用のPVCが作られます。DB Podを削除しても同じPVCに接続するため、タスクが残ります。Lab 02のemptyDirとの違いを比べます。\n\nPVCを削除するとreclaim policyにより保存領域も消え、スキーマだけをmigrationで戻すことになります。PVはノード喪失を含めた可用性の保証ではありません。\n\n→ 実習「3. リソースと保存先を観察する」「6. DB Pod を作り直してもデータが残るか」「B. PVC を削除するとデータはどうなるか」で確かめます。DB Pod を作り直す前に Pod の名前・UID と PVC を記録し、作り直した後と比べます。"),
            section("config", "設定のハッシュと Job の作り直し", "ConfigMap/Secretの内容を変えると名前のハッシュが変わり、Podテンプレートが更新されて新しいPodに置き換わります。旧いConfigMapは自動では消えません。\n\nJobのspec.templateは作成後に変更できないため、参照名が変わるとapplyできません。Alembicのupgrade headは何度実行しても安全なので、構築スクリプトは完了済みJobを削除して作り直します。\n\n→ 実習「7. ConfigMap の変更が Pod にどう反映されるか」「8. 構築スクリプトの再実行（冪等性と migration の再実行）」で確かめます。"),
            section("secret", "Secret が守る範囲と守らない範囲", "SecretはAPIに保存される設定オブジェクトで、base64表現は暗号化ではありません。読み取りやexecができる主体、保存時の保護、配布先をあわせて考えます。\n\nこのクラスターに保存時暗号化は設定していないため、その確認は未検証として記録します。\n\n→ 実習「4. ConfigMap と Secret の参照を確認する」「C. Secret の値だけを変えるとどうなるか」で確かめます。", "実パスワードはリポジトリに含めません。構築スクリプトがローカル専用の値を db.env に生成します。"),
        ], phase_diagram(3))

    add_advanced(add)
    validate(phases)
    return {"title": "WorkBoardで学ぶ Kubernetes / EKS", "phases": phases}


AWS_NOTICE = "AWS の有料リソースを作るコマンドを含みます。ポータルはコマンドを実行しません。README の開始条件（明示的な承認・見積もり・予算通知・削除手順の確認）を満たしてから、自分のターミナルで実行してください。"


def add_advanced(add):
    add(4, "scaling", "増やす・更新する・耐える", "kind 3 ノード・Probe・HPA・PDB・配置制御", "local", 80,
        "レプリカ数だけでは語れない可用性と、計測に基づく調整を、3 ノードの kind で観察します。", [
            concept("Liveness と Readiness", "Liveness はプロセスが動いているかを見て、失敗すると再起動します。Readiness は今リクエストを受けられるかを見て、失敗すると Service の宛先から外れるだけです。", "店員が元気かの確認と、今レジに立てるかの確認"),
            concept("requests / limits", "requests は配置と HPA の使用率の基準になる予約、limits は上限です。CPU は超えると遅くなり、memory は超えると OOMKill されます。", "予約した席数と店の定員"),
            concept("HPA", "使用率を requests で割った値が目標より高ければレプリカを増やします。上限は maxReplicas とノードの空きで決まり、ノード台数ではありません。", "混み具合を見てレジの台数を変える店長"),
            concept("PodDisruptionBudget", "drain などの自発的な退避で、最低何 Pod を残すかを決めます。ノード故障や Pod の直接削除は止められません。", "同時に休めるのは 1 人までという休暇ルール"),
        ], [
            section("availability", "同じ場所に増やすだけでは足りない", "新しい専用クラスター workboard-phase4（control-plane 1 + worker 2）で行います。Phase 3 の workboard-phase3 は変更しません。WorkBoard は 8082 番です。\n\nAPI を 3 Pod にしても同じ Node に載っていれば、その Node の故障で全て止まり得ます。topologySpreadConstraints でノードに分散し、PDB で drain 中に残す数を決めます。DB は 1 Pod のままなので単一障害点として残ります。\n\n→ 実習「3. 配置・Probe・resources を観察する」「F. ノードを drain し、PDB の効果を見る」で確かめます。", "ポータルはコマンドを実行しません。以下は自分のターミナルで実行する手順の抜粋です。"),
            section("measurement", "測ってから数値を決める", "負荷生成 Pod で API に負荷をかけ、HPA が Pod を増やし、負荷を止めると戻る様子を記録します。Rolling Update と rollback では、更新中の HTTP 応答と残っている Pod 数を watch-http で同じ時間軸に並べます。\n\nport-forward は Service を指定しても 1 つの Web Pod に固定されます。その Pod が退避されると計測自体が途切れるため、結果を読むときに区別します。\n\n→ 実習「4. metrics-server と使用量」「6. HTTP 応答を記録しながら Rolling Update を観察する」「D. CPU 負荷を与えて HPA を観察する」「E. 存在しないイメージで更新し、rollback する」で確かめます。"),
        ], phase_diagram(4))

    add(5, "security", "権限と通信を絞る", "kind + Calico・RBAC・NetworkPolicy・PSS・Runbook", "local", 80,
        "誰が何をできるかと、どこへ通信できるかを別々に設定し、許可と拒否の両方を確かめます。", [
            concept("Pod Security Standards", "Namespace のラベルで、Pod の作成時に root や特権などの危険な設定を検査し、拒否・警告・監査します。enforce は Pod にだけ効き、warn と audit は Deployment などにも効きます。", "建物の入口の持ち物検査"),
            concept("RBAC", "Role は何ができるか、RoleBinding は誰にそれを与えるかを決めます。Role があっても Binding がなければ権限はありません。", "鍵のリストと、鍵を渡す相手の名簿"),
            concept("NetworkPolicy と CNI", "NetworkPolicy は通信の許可ルールを書く API オブジェクトで、実際に遮断するのは CNI です。対応しない CNI では作成できても効きません。", "規則書と、それを守らせる警備員"),
            concept("securityContext", "非 root、読み取り専用のルート、capability の削除、権限昇格の禁止で、侵入されたときの影響を小さくします。Secret を読める人の問題は別です。", "包丁は使えても倉庫の鍵は持たない料理人"),
        ], [
            section("boundaries", "権限と通信は別の境界", "新しい専用クラスター workboard-phase5 は既定の CNI を外し、Calico を入れて NetworkPolicy を有効にします。WorkBoard は 8083 番です。\n\nRBAC で API 操作を制限しても、アプリの通信まで閉じるわけではありません。default deny に必要な通信だけを足し、許可した経路が通ることと、許可していない経路がタイムアウトすることの両方を確かめます。\n\n→ 実習「4. Pod Security Standards の拒否を確かめる」「5. ServiceAccount と RBAC を確かめる」「6. NetworkPolicy の許可と拒否を確かめる」で確かめます。", "ポータルはコマンドを実行しません。以下は自分のターミナルで実行する手順の抜粋です。"),
            section("diagnose", "症状から層を切り分ける", "イメージ取得失敗ならイベントとタグ、通信失敗なら名前解決・EndpointSlice・ポート・NetworkPolicy、権限不足なら主体と RoleBinding を追います。runbook.md に、症状・観察コマンド・原因・復旧・再発防止を障害ごとにまとめてあります。\n\nPod が Ready でも、kubelet の Probe は NetworkPolicy の影響を受けないため、アプリ間の通信は遮断され得ます。\n\n→ 実習「A. 存在しない image tag」「B. 誤った Service selector」「E. memory limit による OOMKilled」で確かめます。"),
        ], phase_diagram(5))

    add(6, "eks", "AWS上の責任を分ける", "Terraform・VPC・EKS・Managed Node Group・ECR", "cloud", 120,
        "マネージドサービスでも残る責任と、費用・公開範囲を設計し、承認を得てから構築します。", [
            concept("責任共有（Managed Node Group）", "ノードの作成やドレイン付き更新は EKS が支援しますが、AMI の切り替え・台数・脆弱性対応は利用者の責任です。", "賃貸マンションの管理会社と入居者"),
            concept("public/private subnet と NAT", "private subnet のノードはインターネットから直接見えず、外向きの通信やイメージ取得は NAT を通ります。", "受付だけが外に面した建物と社員用の通用口"),
            concept("access entries", "IAM の権限とは別に、Kubernetes 側の管理権限を IAM 主体へ明示的に付けます。", "建物に入る許可と金庫室に入る許可"),
            concept("plan と state", "plan は変更の予告、state は Terraform が管理している資産の台帳です。台帳を失うと削除もできなくなります。", "工事の見積書と設備の管理台帳"),
        ], [
            section("responsibility", "まず標準 EKS で境界を見る", "Terraform は AWS provider のリソースで VPC・EKS・Managed Node Group・IAM・ECR を明示的に書いています。community module を使わないのは、構成要素を一つずつ読むためです。\n\nAPI endpoint は public のまま CIDR で制限し、0.0.0.0/0 は拒否します。WorkBoard は ECR のイメージで動かし、入口は port-forward（8086 番）だけです。DB は Phase 7 で RDS に移すため、ここでは使い捨ての Postgres です。\n\n→ 実習「1. 適用前に読む（AWS に接続しない）」「3. kubeconfig を作り、クラスターを観察する」「6. ネットワークと権限を観察する」で確かめます。", AWS_NOTICE),
            section("cost", "費用と後片付けを先に決める", "cost-estimate.md に region・稼働時間・台数・AZ 構成をそろえた見積もりの観点があります。料金は公式ページで確認し、確認できない値は要確認のまま残します。予算通知は課金停止の保証ではありません。\n\naws-cleanup.md に、destroy の順序と、ALB・ENI・EBS・NAT・EIP・ECR・ロググループなど残り得る資産の点検手順があります。\n\n→ 実習「2. （承認後）`terraform plan` の差分を読む」「後片付け・再構築」で確かめます。", "削除は元に戻せません。aws-cleanup.md の手順で、対象と消えるデータを確認してから自分で実行してください。"),
        ], phase_diagram(6))

    add(7, "integration", "AWSサービスをつなぐ", "RDS・ALB・AWS Load Balancer Controller・Pod Identity・Helm", "cloud", 120,
        "入口・データ・権限をマネージドサービスとどう分担するかを決め、公開範囲を絞って確かめます。", [
            concept("RDS（DB の外部化）", "パッチ・バックアップ・フェイルオーバーを AWS に任せる代わりに、費用と AWS 依存が増えます。接続やデータ保護の設計は残ります。", "自炊をやめて給食センターと契約する"),
            concept("Pod Identity", "特定の Namespace と ServiceAccount だけに IAM ロールを結び付け、一時的な認証情報を渡します。", "社員証ではなく部署限定の入館カード"),
            concept("Helm（chart の利用者として）", "helm template で中身を読んでから、release 単位で install・history・rollback します。", "組み立て説明書を先に読み、作業を番号付きで記録する"),
            concept("Ingress と ALB", "Ingress は API オブジェクトで、実際に ALB を作るのは Controller です。公開は許可した IP に限り、検証後は Ingress を先に消します。", "注文票と、それを受けて店を開ける店長"),
        ], [
            section("path", "入口とDBをクラスターの外へ", "Phase 6 のクラスターが稼働していることが前提です。Phase 7 の Terraform は Phase 6 のファイルや state を読まず、クラスター名などの変数と data source で既存の環境を参照し、RDS・Pod Identity Agent・Controller 用の IAM ロールを足します。\n\nRDS のマスターパスワードは Secrets Manager が管理し、state にも Git にも平文を残しません。接続は PGSSLMODE=require で TLS を使います。ALB の health check は / で、DB 障害で全ターゲットが外れないようにしています。\n\n→ 実習「2. Helm chart の中身を読む（AWS に接続しない）」「6. ALB と公開範囲を確認する」「7. RDS を観察する」で確かめます。", AWS_NOTICE),
            section("identity", "公開と権限を限定する", "認証のない WorkBoard を恒常的にインターネットへ公開しません。inbound-cidrs で学習者の IP に絞り、検証が終わったら Ingress を削除して ALB を消します。\n\nhelm history で release の履歴を見て、rollback の単位を確かめます。S3 への CSV エクスポートと Redis + Worker は任意の発展課題で、README に設計の観点だけを置いています。\n\n→ 実習「4. kubeconfig を作り、Controller を導入する」「6. ALB と公開範囲を確認する」「D. Ingress を削除して、ALB が消えることを確認する」で確かめます。", AWS_NOTICE),
        ], phase_diagram(7))

    add(8, "pipeline", "変更と運用をつなぐ", "CI/CD・Argo CD・Prometheus・SLO", "review", 100,
        "変更を安全に届け、観察し、戻すまでを一つの流れにします。GitOps と監視は kind で試します。", [
            concept("CI / CD", "CI はテスト・ビルド・マニフェストの検証、CD は環境への反映です。CD は手動承認制にし、AWS へは OIDC の一時認証で接続します。", "出荷検査と配送の工程"),
            concept("GitOps（Argo CD）", "Git の定義と実環境の差を検出し、同期で Git の状態に合わせます。戻すときは Git を revert します。", "正本の台帳と現物を照合する係"),
            concept("Prometheus と PromQL", "API の /metrics から定期的に値を集め、リクエスト率・エラー率・p95 応答時間を式で求めます。", "定期的に検針して使用量を計算する係"),
            concept("SLI / SLO", "SLI は利用者から見た指標、SLO はその目標値です。分子・分母・除外条件・期間を決め、測る前に達成とは言いません。", "測った所要時間と約束する所要時間"),
        ], [
            section("delivery", "テスト・反映・復旧を切り分ける", ".github/workflows/ci.yaml は push と pull request でテスト・ビルド・kustomize・Terraform・スクリプトを検証します。cd.yaml は手動実行だけで、GitHub の environment の承認を待ってから ECR に push し EKS に適用します。AWS 側の準備をするまでは動きません。\n\nArgo CD は専用クラスター workboard-phase8 で試します。同期対象は GitHub 上のリポジトリなので、自分の fork に push するまで同期できません。DB のパスワードは Git に置かず、構築スクリプトが Secret を事前に作ります。\n\n→ 実習「5. Argo CD を開き、push 前の状態を確認する」「6. 同期、drift、revert を観察する」「7. CI をローカルで再現する」「A. 手動の変更（drift）を検出し、直す」で確かめます。", "ポータルはコマンドを実行しません。以下は自分のターミナルで実行する手順の抜粋です。"),
            section("observe", "測った事実で改善する", "Prometheus は kubernetes_sd で API の Pod を見つけ、/metrics を集めます。slo.md に、ヘルスチェックを除いた成功率と p95 応答時間の定義があります。\n\nNginx が返す 504/502 は API に届かないため、API のメトリクスには現れません。メトリクスで分からないことは、ログやイベントで補います。\n\n→ 実習「3. WorkBoard とメトリクスを確認する」「4. PromQL でリクエスト率・エラー率・p95 を求める」「C. DB のロックで遅延を作り、p95 の変化を観察する」で確かめます。"),
        ], phase_diagram(8))

    add(9, "comparison", "ECSとEKSを選び分ける", "同じ要件で採用判断を書く", "review", 90,
        "EKS 採用を正解にせず、同じ要件・同じ条件・根拠で選択肢を比べます。", [
            concept("同一条件での比較", "要件・region・稼働時間・構成・調査日をそろえて ECS 案と EKS 案を評価します。条件の違う数字は比べません。", "同じ距離・同じ荷物で電車とバスを比べる"),
            concept("責任共有と運用人件費", "マネージドの範囲が違えば、自分たちが担うパッチ・容量・アドオンの工数が変わります。利用料に加え、人の時間と学習負担もコストです。", "家賃が安くても管理を全部自分でやる物件"),
            concept("判断が変わる条件", "結論を一つの正解にせず、どの仮定が変わると逆転するかを残します。反対案を最も有利な条件で擁護して確かめます。", "雨なら中止と条件を付けた予定"),
        ], [
            section("scenario", "同じサービス要件で比較する", "ecs-vs-eks.md の課題シナリオは、月間数十万リクエスト規模の社内タスク管理を少人数で運用し、将来複数サービスが加わる可能性がある状況です。これはユーザーの実要件ではなく、比較のための仮定です。\n\narchitecture.md で同じ WorkBoard を ECS と EKS に載せた構成を比べ、Phase 1〜8 で観察したことを根拠として使います。このラボは AWS もクラスターも操作しません。\n\n→ 実習「1. 構成要素と責任分界を公式資料で確認する」で確かめます。"),
            section("decision", "採用案を反対案と一緒に書く", "採用案だけでなく、もう一方を選ばない理由と、その判断が変わる条件も残します。既存技術や組織の習熟度も要件の一部です。\n\n料金は AWS Pricing Calculator と公式料金ページで、region・時間・構成・調査日をそろえて自分で確認します。教材には料金の値を載せていません。\n\n→ 実習「2. 費用を同じ条件で見積もる」「4. 反対意見を試す」で確かめます。"),
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
        assert phase["implemented"]
        assert phase["goals"] and phase["questions"] and phase["memoFields"]
        assert all(q["prompt"] and q["rubric"] for q in phase["questions"])
        assert all((ROOT / source["path"]).is_file() for source in phase["sources"])
        validate_diagram(phase["diagram"])
        practice = [s for s in phase["sections"] if s.get("kind") == "practice"]
        # Phase 9 は AWS もクラスターも操作しない机上の比較で、実行コマンドがない。
        assert practice and (phase["id"] == 9 or any(s.get("steps") for s in practice))
        assert len({s["id"] for s in phase["sections"]}) == len(phase["sections"])
        assert all(not any(word in s["title"] for word in ("学習メモ", "回答", "実装時")) for s in practice)


if __name__ == "__main__":
    output = Path(__file__).with_name("curriculum.json")
    output.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("教材を生成しました: Phase 0〜9 / ラボは読み取りのみ")
