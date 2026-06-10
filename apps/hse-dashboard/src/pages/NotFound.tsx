import { Link } from "react-router-dom";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="The page you are looking for does not exist or has moved."
      action={
        <Link to="/procedures">
          <Button variant="primary">Back to procedures</Button>
        </Link>
      }
    />
  );
}
