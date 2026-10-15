import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, setSession } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [notice, setNotice] = useState("");
  const expiry = useRef(null);

  function logout(message = "") {
    clearTimeout(expiry.current);
    setSession(null);
    setUser(null);
    setNotice(message);
  }

  async function login(credentials) {
    const token = await api("/auth/login", {
      method: "POST",
      body: credentials,
    });
    setSession(token.access_token, () =>
      logout("Your session expired. Please sign in again."),
    );
    try {
      const current = await api("/auth/me");
      setUser(current);
      setNotice("");
      clearTimeout(expiry.current);
      expiry.current = setTimeout(
        () => logout("Your session expired. Please sign in again."),
        token.expires_in * 1000,
      );
      return current;
    } catch (error) {
      logout();
      throw error;
    }
  }

  useEffect(
    () => () => {
      clearTimeout(expiry.current);
      setSession(null);
    },
    [],
  );

  return (
    <AuthContext.Provider value={{ user, setUser, notice, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
