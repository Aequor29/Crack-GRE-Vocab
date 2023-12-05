import { Card, CardBody } from "@nextui-org/react";
import { Button } from "@nextui-org/button";
export default function DashBoardPage() {
  return (
    <div className="flex flex-col justify-center items-center my-4">
      <h2>Dashboard</h2>
      <div>
        <Card>
          <CardBody>
            <p>Hi This is time to study GRE!</p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
