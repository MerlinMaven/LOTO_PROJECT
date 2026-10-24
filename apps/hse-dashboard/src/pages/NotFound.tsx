import { Link } from "react-router-dom";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export function NotFound() {
  return (
    <EmptyState
      title="Page introuvable"
      description="La page que vous recherchez n'existe pas ou a été déplacée."
      action={
        <Link to="/procedures">
          <Button variant="primary">Retour aux procédures</Button>
        </Link>
      }
    />
  );
}
