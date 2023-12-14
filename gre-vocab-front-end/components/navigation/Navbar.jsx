"use client";
import {
  Navbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  NavbarMenuToggle,
  NavbarMenu,
  NavbarMenuItem,
  Button,
  Link,
} from "@nextui-org/react";
import ThemeSwitch from "@/components/themeSwitch";
import React, { useState } from "react";
import { useAuth } from "@/app/AuthContext";

export default function Nav() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const { isLoggedIn, setIsLoggedIn } = useAuth();

  const signOut = () => {
    localStorage.removeItem("token");
    setIsLoggedIn(false);
  };

  const menuItems = [
    { label: "Learn", path: "/Learning" },
    { label: "Review", path: "/Reviewing" },
    { label: "Dashboard", path: "/dashboard" },
  ];

  return (
    <Navbar className="shadow-md dark:shadow-dark">
      <NavbarContent>
        <NavbarMenuToggle
          aria-label={isMenuOpen ? "Close menu" : "Open menu"}
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className="sm:hidden"
        />
        <NavbarBrand>
          <img src="logo.svg" alt="Logo" />
          <p className="font-bold text-inherit">Crack-GRE</p>
        </NavbarBrand>

        {/* Items for larger screens */}
        <NavbarContent className="hidden sm:flex gap-4" justify="center">
          {menuItems.map((item, index) =>
            !item.hiddenWhenLoggedIn || !isLoggedIn ? (
              <NavbarItem key={index}>
                <Link color="foreground" href={item.path}>
                  {item.label}
                </Link>
              </NavbarItem>
            ) : null
          )}
        </NavbarContent>

        <NavbarContent justify="end">
          <NavbarItem className=" lg:flex">
            <ThemeSwitch />
          </NavbarItem>
          {!isLoggedIn ? (
            <>
              <NavbarItem className="hidden lg:flex">
                <Link href="/SignUp">Sign Up</Link>
              </NavbarItem>
              <NavbarItem>
                <Button as={Link} color="primary" href="/Login" variant="flat">
                  Login
                </Button>
              </NavbarItem>
            </>
          ) : (
            <NavbarItem>
              <Button color="danger" onClick={signOut}>
                Logout
              </Button>
            </NavbarItem>
          )}
        </NavbarContent>
      </NavbarContent>

      {/* Items for the toggle menu */}
      <NavbarMenu isOpen={isMenuOpen}>
        {menuItems.map((item, index) =>
          !item.hiddenWhenLoggedIn || !isLoggedIn ? (
            <NavbarMenuItem key={index}>
              <Link
                href={item.path}
                className="w-full"
                onClick={() => setIsMenuOpen(false)}
              >
                {item.label}
              </Link>
            </NavbarMenuItem>
          ) : null
        )}
        {isLoggedIn ? null : (
          <NavbarMenuItem>
            <Link
              href="/SignUp"
              className="w-full"
              onClick={() => setIsMenuOpen(false)}
            >
              Sign Up
            </Link>
          </NavbarMenuItem>
        )}
        {isLoggedIn ? (
          <NavbarMenuItem>
            <Link
              color="danger"
              onClick={() => {
                signOut();
                setIsMenuOpen(false);
              }}
            >
              Logout
            </Link>
          </NavbarMenuItem>
        ) : null}
      </NavbarMenu>
    </Navbar>
  );
}
