const kubernetesResources = new Set([
  "pod", "deployment", "replicaset", "service", "job", "statefulset", "pvc", "pv",
  "configmap", "secret", "hpa", "networkpolicy", "serviceaccount", "namespace", "volume",
  "role", "clusterrole", "node", "controlplane", "api",
]);

const symbols: Record<string, string> = {
  browser: "M2 4h20v14H2V4Zm6 18h8m-4-4v4M2 8h20",
  container: "M3 4h18v16H3V4Zm0 4h18M7 12l-2 2 2 2m10-4 2 2-2 2m-6 1 2-6",
  document: "M5 2h10l4 4v16H5V2Zm10 0v5h4M8 11h8m-8 4h8m-8 4h5",
  database: "M3 6c0-5 18-5 18 0v12c0 5-18 5-18 0V6Zm0 0c0 5 18 5 18 0M3 12c0 5 18 5 18 0",
  storage: "M3 4h18v16H3V4Zm0 6h18M7 7h1m-1 7h1m3 0h6",
  pipeline: "M2 6h6v6H2V6Zm14 6h6v6h-6v-6ZM8 9h7v6h1m-5-9 3 3-3 3",
  metrics: "M3 3v18h18M7 17v-5m5 5V7m5 10v-8",
  cloud: "M6 19a5 5 0 1 1 0-10 7 7 0 0 1 13-1 5.5 5.5 0 0 1-1 11H6Z",
  terminal: "M2 4h20v16H2V4Zm4 5 3 3-3 3m5 0h6",
  identity: "M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6l-9-4Zm-4 10 3 3 5-6",
};

export function resourceTitle(resource?: string) {
  const explicit: Record<string, string> = {
    browser: "利用者の画面", container: "container", document: "資料・定義",
    "kubernetes.pod": "Pod", "kubernetes.deployment": "Deployment", "kubernetes.replicaset": "ReplicaSet",
    "kubernetes.service": "Service", "kubernetes.job": "Job", "kubernetes.statefulset": "StatefulSet",
    "kubernetes.pvc": "PersistentVolumeClaim", "kubernetes.pv": "PersistentVolume",
    "kubernetes.configmap": "ConfigMap", "kubernetes.secret": "Secret", "kubernetes.hpa": "HPA",
    "kubernetes.networkpolicy": "NetworkPolicy", "kubernetes.serviceaccount": "ServiceAccount",
    "storage.emptydir": "emptyDir volume", "storage.volume": "名前付き volume",
    "aws.rds": "Amazon RDS", "aws.alb": "Application Load Balancer", "aws.eks": "Amazon EKS",
  };
  return resource ? explicit[resource] || resource.split(".").at(-1)! : "構成要素";
}

export function ResourceSymbol({ resource, kind, size = 38 }: { resource?: string; kind?: string; size?: number }) {
  const name = resource?.startsWith("kubernetes.") ? resource.slice("kubernetes.".length).toLowerCase() : "";
  if (kubernetesResources.has(name)) return <img src={`/icons/kubernetes/${name}.svg`} width={size} height={size} alt={`${resourceTitle(resource)} の公式アイコン`} className="resource-icon" />;
  const aws = resource?.startsWith("aws.") ? resource.slice("aws.".length) : "";
  if (["eks", "ecs", "ecr", "rds", "ec2", "iam", "vpc", "alb"].includes(aws)) return <img src={`/icons/aws/${aws}.svg`} width={size} height={size} alt={`${resourceTitle(resource)} の公式アイコン`} className="resource-icon" />;
  const semantic = resource === "storage.emptydir" || resource === "storage.volume" ? "storage"
    : resource === "aws.rds" || resource === "database" ? "database"
    : resource?.startsWith("aws.") ? "cloud" : resource || kind || "document";
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="resource-symbol"><path d={symbols[semantic] || symbols.document} /></svg>;
}
