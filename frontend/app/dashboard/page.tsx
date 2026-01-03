"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { api, type TaskKind } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

function statusBadge(status: string) {
  if (status === "success") return <Badge variant="default">成功</Badge>;
  if (status === "failed") return <Badge variant="danger">失败</Badge>;
  if (status === "running") return <Badge variant="warning">运行中</Badge>;
  return <Badge variant="secondary">等待</Badge>;
}

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<{ authed: boolean; user?: string }>({ authed: false });
  const [configYaml, setConfigYaml] = useState<string>("");
  const [configMsg, setConfigMsg] = useState<string>("");
  const [tasks, setTasks] = useState<Array<{ id: string; kind: TaskKind; status: string; message: string }>>(
    []
  );
  const [artifacts, setArtifacts] = useState<Array<{ name: string; size: number; mtime: number }>>([]);
  const [logs, setLogs] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const actions: Array<{ kind: TaskKind; title: string; desc: string }> = useMemo(
    () => [
      { kind: "update-data", title: "更新数据", desc: "把ETF日线拉取并缓存到本地（可复现）。" },
      { kind: "plan-weekly", title: "生成周计划", desc: "周五生成下周目标权重（给你手动下单用）。" },
      { kind: "run-paper", title: "运行纸交易", desc: "按统一假设记账一次，生成交易清单与纸账户。" },
      { kind: "run-backtest", title: "运行回测", desc: "用历史数据验证收益/回撤/成本影响。" }
    ],
    []
  );

  async function refreshAll() {
    const [meRes, cfg, taskRes, artRes, logRes] = await Promise.allSettled([
      api.me(),
      api.getConfig(),
      api.listTasks(),
      api.listArtifacts(),
      api.tailLogs(300)
    ]);
    if (meRes.status === "fulfilled") setMe(meRes.value);
    if (cfg.status === "fulfilled") setConfigYaml(cfg.value.yaml);
    if (taskRes.status === "fulfilled") setTasks(taskRes.value.tasks);
    if (artRes.status === "fulfilled") setArtifacts(artRes.value.artifacts);
    if (logRes.status === "fulfilled") setLogs(logRes.value);
  }

  useEffect(() => {
    refreshAll().catch(() => {});
  }, []);

  useEffect(() => {
    if (me.authed === false) return;
  }, [me.authed]);

  useEffect(() => {
    api
      .me()
      .then((r) => {
        setMe(r);
        if (!r.authed) router.replace("/login");
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  async function runTask(kind: TaskKind) {
    setBusy(true);
    try {
      const { task_id } = await api.createTask(kind);
      for (;;) {
        const t = await api.getTask(task_id);
        await refreshAll();
        if (t.status === "success" || t.status === "failed") break;
        await new Promise((r) => setTimeout(r, 800));
      }
    } finally {
      setBusy(false);
      await refreshAll().catch(() => {});
    }
  }

  async function saveConfig() {
    setConfigMsg("");
    setBusy(true);
    try {
      const r = await api.putConfig(configYaml);
      setConfigMsg(`已保存（备份：${r.backup}）`);
    } catch (e) {
      setConfigMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function doLogout() {
    await api.logout().catch(() => {});
    router.replace("/login");
  }

  return (
    <div className="space-y-6 pb-10">
      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-600">当前用户：{me.user || "—"}</div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => refreshAll().catch(() => {})} disabled={busy}>
            刷新
          </Button>
          <Button variant="outline" onClick={doLogout}>
            退出登录
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>核心操作</CardTitle>
          <CardDescription>你每周主要用“更新数据 + 生成周计划 + 纸交易记账”。回测只需偶尔跑。</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {actions.map((a) => (
            <div key={a.kind} className="rounded-lg border border-slate-200 p-4">
              <div className="flex items-center justify-between">
                <div className="font-medium">{a.title}</div>
                <Button onClick={() => runTask(a.kind)} disabled={busy}>
                  运行
                </Button>
              </div>
              <div className="mt-2 text-sm text-slate-600">{a.desc}</div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>配置</CardTitle>
          <CardDescription>可直接编辑 YAML（ETF池/窗口/风控/成本等）。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea value={configYaml} onChange={(e) => setConfigYaml(e.target.value)} className="min-h-[280px]" />
          <div className="flex items-center gap-3">
            <Button onClick={saveConfig} disabled={busy}>
              保存配置
            </Button>
            {configMsg ? <div className="text-sm text-slate-600">{configMsg}</div> : null}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>任务</CardTitle>
            <CardDescription>最近 50 条任务状态。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {tasks.length === 0 ? <div className="text-sm text-slate-500">暂无任务</div> : null}
            {tasks.map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded border border-slate-200 px-3 py-2">
                <div className="text-sm">
                  <div className="font-medium">{t.kind}</div>
                  <div className="text-slate-500">{t.id.slice(0, 8)}</div>
                </div>
                <div className="flex items-center gap-2">
                  {statusBadge(t.status)}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>产物</CardTitle>
            <CardDescription>回测报告/计划单/交易清单等文件。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {artifacts.length === 0 ? <div className="text-sm text-slate-500">暂无产物</div> : null}
            {artifacts.map((a) => (
              <div key={a.name} className="flex items-center justify-between rounded border border-slate-200 px-3 py-2">
                <div className="text-sm">
                  <div className="font-medium">{a.name}</div>
                  <div className="text-slate-500">{Math.round(a.size / 1024)} KB</div>
                </div>
                <Button variant="secondary" asChild>
                  <Link href={`/api/artifacts/${encodeURIComponent(a.name)}`} target="_blank">
                    打开/下载
                  </Link>
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>日志</CardTitle>
          <CardDescription>仅显示末尾 300 行（便于排错）。</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="max-h-[360px] overflow-auto rounded-md border border-slate-200 bg-slate-950 p-3 text-xs text-slate-100">
            {logs || "（暂无日志）"}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}

