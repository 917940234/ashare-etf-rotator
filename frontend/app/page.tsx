import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="py-10">
      <Card>
        <CardHeader>
          <CardTitle>开始使用</CardTitle>
          <CardDescription>先登录，再在控制台里完成数据更新、周计划、纸交易与回测。</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Button asChild>
            <Link href="/login">登录</Link>
          </Button>
          <Button variant="secondary" asChild>
            <Link href="/dashboard">进入控制台</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

