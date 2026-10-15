import {
  BrowserRouter,
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";
import LandingPage from "./App";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import DashboardLayout from "./components/DashboardLayout";
import AuthPage from "./pages/AuthPage";
import {
  StudentDashboard,
  StudentProfile,
  WindowManager,
} from "./pages/StudentPages";
import {
  EmployeeDirectory,
  EmployeeProfile,
  SupervisorDashboard,
} from "./pages/SupervisorPages";
import "./dashboard.css";
import { LocationManager, RequirementManager } from "./pages/StaffingPages";
import { ScheduleGenerator, StudentSchedule } from "./pages/SchedulePages";

function Protected({ role }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role)
    return (
      <Navigate
        to={user.role === "student" ? "/student" : "/supervisor"}
        replace
      />
    );
  return <Outlet />;
}

function Guest({ register = false }) {
  const { user } = useAuth();
  return user ? (
    <Navigate
      to={user.role === "student" ? "/student" : "/supervisor"}
      replace
    />
  ) : (
    <AuthPage key={register ? "register" : "login"} register={register} />
  );
}

export default function Router() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Guest />} />
          <Route path="/register" element={<Guest register />} />
          <Route element={<Protected role="student" />}>
            <Route path="/student" element={<DashboardLayout />}>
              <Route index element={<StudentDashboard />} />
              <Route path="profile" element={<StudentProfile />} />
              <Route path="schedule" element={<StudentSchedule />} />
              <Route
                path="classes"
                element={<WindowManager key="classes" kind="classes" />}
              />
              <Route
                path="availability"
                element={
                  <WindowManager key="availability" kind="availability" />
                }
              />
            </Route>
          </Route>
          <Route element={<Protected role="supervisor" />}>
            <Route path="/supervisor" element={<DashboardLayout />}>
              <Route index element={<SupervisorDashboard />} />
              <Route path="employees" element={<EmployeeDirectory />} />
              <Route path="employees/:id" element={<EmployeeProfile />} />
              <Route path="locations" element={<LocationManager />} />
              <Route path="requirements" element={<RequirementManager />} />
              <Route path="schedules" element={<ScheduleGenerator />} />
            </Route>
          </Route>
          <Route
            path="*"
            element={
              <main className="auth-shell">
                <h1>Page not found.</h1>
                <Link to="/">Return to CampusShift</Link>
              </main>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
