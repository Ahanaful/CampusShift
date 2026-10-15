import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const root = user.role === "student" ? "/student" : "/supervisor";
  const links =
    user.role === "student"
      ? [
          [root, "Overview"],
          [root + "/classes", "My classes"],
          [root + "/availability", "My availability"],
          [root + "/profile", "My profile"],
        ]
      : [
          [root, "Overview"],
          [root + "/employees", "Employee directory"],
        ];
  return (
    <div className="dashboard-shell">
      <aside className="sidebar">
        <Link className="brand" to="/">
          CampusShift<span className="brand-period">.</span>
        </Link>
        <button
          className="menu-toggle secondary-button"
          aria-expanded={menuOpen}
          aria-controls="workspace-nav"
          onClick={() => setMenuOpen(!menuOpen)}
        >
          Menu
        </button>
        <nav
          id="workspace-nav"
          className={menuOpen ? "is-open" : ""}
          aria-label="Workspace navigation"
        >
          {links.map(([to, label]) => (
            <NavLink
              end={to === root}
              key={to}
              to={to}
              onClick={() => setMenuOpen(false)}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-account">
          <span className="role-badge">{user.role}</span>
          <strong>{user.full_name}</strong>
          <span>{user.email}</span>
          <button className="secondary-button" onClick={() => logout()}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="dashboard-main">
        <div className="workspace-topbar">
          <span>
            Campus community /{" "}
            {user.role === "student"
              ? "Student workspace"
              : "Department workspace"}
          </span>
          <span>Phase 02</span>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
