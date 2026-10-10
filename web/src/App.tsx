import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function App() {
	return (
		<main className="mx-auto max-w-3xl p-8">
			<Card>
				<CardHeader>
					<CardTitle>Cressey</CardTitle>
				</CardHeader>
				<CardContent>
					<Badge variant="secondary">
						Le triangle de la fraude, appliqué aux agents IA
					</Badge>
				</CardContent>
			</Card>
		</main>
	);
}
