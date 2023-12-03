import { Card, CardBody } from "@nextui-org/react";
import { Button } from "@nextui-org/button";
export default function DashBoardPage() {
  return (
    <div className="container mx-auto px-6">
      <h1>Dashboard</h1>
      <div>
        <Card>
          <CardBody>
            <p>Card body</p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
