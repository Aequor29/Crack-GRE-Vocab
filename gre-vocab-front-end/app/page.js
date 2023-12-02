"use client";

import * as React from "react";
import {NextUIProvider} from "@nextui-org/react";
import DashBoardPage from "./dashboard/page";

export default function Home() {
  return (
    <NextUIProvider>
      <main className="flex min-h-screen flex-col items-center justify-between p-24">
        <DashBoardPage/>
      </main>
    </NextUIProvider>
  )
}
