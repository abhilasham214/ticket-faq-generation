import type { Cluster } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface ClusterCardProps {
  cluster: Cluster;
}

export function ClusterCard({ cluster }: ClusterCardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle>{cluster.theme_title}</CardTitle>
          <Badge variant="secondary">{cluster.ticket_count} tickets</Badge>
        </div>
        {cluster.top_terms.length > 0 && (
          <CardDescription>{cluster.top_terms.join(", ")}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div>
          <p className="text-sm font-medium">{cluster.faq.question}</p>
          <p className="mt-1 text-sm text-muted-foreground">{cluster.faq.answer}</p>
        </div>
        <Collapsible>
          <CollapsibleTrigger className="text-left text-xs font-medium text-muted-foreground underline underline-offset-2 hover:text-foreground">
            Show source tickets ({cluster.ticket_ids.length})
          </CollapsibleTrigger>
          <CollapsibleContent>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {cluster.ticket_ids.map((id) => (
                <li key={id}>
                  <Badge variant="outline">{id}</Badge>
                </li>
              ))}
            </ul>
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
}
