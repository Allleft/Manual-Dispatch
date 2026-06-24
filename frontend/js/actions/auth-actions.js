import {
  apiLoginAccount,
  apiRegisterAccount,
  apiResetPassword,
} from "../api/manual-dispatch-api.js";
import {
  AUTH_ACCOUNT_ID_SESSION_KEY,
  AUTH_ACCOUNT_NAME_SESSION_KEY,
} from "../state/app-state.js";

function getSafeSessionStorage() {
  try {
    return window.sessionStorage;
  } catch (error) {
    return null;
  }
}

export function createAuthActions({
  state,
  renderAuthGate,
  renderBoard,
  onAuthenticated = () => {},
}) {
  function restoreAccountSession() {
    const storage = getSafeSessionStorage();
    if (!storage) {
      return;
    }

    const accountName = storage.getItem(AUTH_ACCOUNT_NAME_SESSION_KEY) || "";
    const accountId = storage.getItem(AUTH_ACCOUNT_ID_SESSION_KEY) || "";
    if (!accountName) {
      return;
    }

    state.accountName = accountName;
    state.accountId = accountId;
    state.isLoggedIn = true;
  }

  function saveAccountSession(identity) {
    const storage = getSafeSessionStorage();
    if (!storage) {
      return;
    }

    storage.setItem(AUTH_ACCOUNT_NAME_SESSION_KEY, identity.account_name || "");
    storage.setItem(AUTH_ACCOUNT_ID_SESSION_KEY, String(identity.account_id || ""));
  }

  function clearAccountSession() {
    const storage = getSafeSessionStorage();
    if (!storage) {
      return;
    }

    storage.removeItem(AUTH_ACCOUNT_NAME_SESSION_KEY);
    storage.removeItem(AUTH_ACCOUNT_ID_SESSION_KEY);
  }

  function applyLoggedInAccount(identity) {
    state.accountName = identity.account_name || "";
    state.accountId = identity.account_id ? String(identity.account_id) : "";
    state.isLoggedIn = Boolean(state.accountName);
    state.loginError = "";
    state.registerError = "";
    state.resetError = "";
    state.authSuccessMessage = "";
    saveAccountSession(identity);
  }

  function logoutAccount() {
    state.accountName = "";
    state.accountId = "";
    state.isLoggedIn = false;
    state.authMode = "login";
    state.loginError = "";
    state.registerError = "";
    state.resetError = "";
    state.authSuccessMessage = "";
    clearAccountSession();
    renderBoard();
  }

  async function handleLogin(event) {
    event.preventDefault();
    if (state.isAuthLoading) {
      return;
    }

    const form = event.currentTarget;
    const accountNameInput = form.querySelector('input[name="account_name"]');
    const passwordInput = form.querySelector('input[name="password"]');
    const accountName = accountNameInput ? accountNameInput.value.trim() : "";
    const password = passwordInput ? passwordInput.value : "";

    state.isAuthLoading = true;
    state.loginError = "";
    state.authSuccessMessage = "";
    renderAuthGate();

    try {
      const identity = await apiLoginAccount({ account_name: accountName, password });
      applyLoggedInAccount(identity);
      onAuthenticated();
    } catch (error) {
      state.loginError = error.message || "Invalid account name or password";
    } finally {
      if (passwordInput) {
        passwordInput.value = "";
      }
      state.isAuthLoading = false;
      renderBoard();
    }
  }

  async function handleRegister(event) {
    event.preventDefault();
    if (state.isAuthLoading) {
      return;
    }

    const form = event.currentTarget;
    const accountNameInput = form.querySelector('input[name="account_name"]');
    const passwordInput = form.querySelector('input[name="password"]');
    const confirmPasswordInput = form.querySelector('input[name="confirm_password"]');
    const accountName = accountNameInput ? accountNameInput.value.trim() : "";
    const password = passwordInput ? passwordInput.value : "";
    const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : "";

    state.isAuthLoading = true;
    state.registerError = "";
    state.authSuccessMessage = "";
    renderAuthGate();

    try {
      const identity = await apiRegisterAccount({
        account_name: accountName,
        password,
        confirm_password: confirmPassword,
      });
      applyLoggedInAccount(identity);
      onAuthenticated();
    } catch (error) {
      state.registerError = error.message || "Unable to create account";
    } finally {
      if (passwordInput) {
        passwordInput.value = "";
      }
      if (confirmPasswordInput) {
        confirmPasswordInput.value = "";
      }
      state.isAuthLoading = false;
      renderBoard();
    }
  }

  async function handleResetPassword(event) {
    event.preventDefault();
    if (state.isAuthLoading) {
      return;
    }

    const form = event.currentTarget;
    const accountNameInput = form.querySelector('input[name="account_name"]');
    const resetCodeInput = form.querySelector('input[name="admin_reset_code"]');
    const passwordInput = form.querySelector('input[name="new_password"]');
    const confirmPasswordInput = form.querySelector('input[name="confirm_password"]');
    const accountName = accountNameInput ? accountNameInput.value.trim() : "";
    const adminResetCode = resetCodeInput ? resetCodeInput.value : "";
    const newPassword = passwordInput ? passwordInput.value : "";
    const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : "";

    state.isAuthLoading = true;
    state.resetError = "";
    state.authSuccessMessage = "";
    renderAuthGate();

    try {
      await apiResetPassword({
        account_name: accountName,
        admin_reset_code: adminResetCode,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      state.authMode = "login";
      state.authSuccessMessage = "Password reset successfully. Please log in with your new password.";
    } catch (error) {
      state.resetError = "Unable to reset password. Please check your details or contact an administrator.";
    } finally {
      if (resetCodeInput) {
        resetCodeInput.value = "";
      }
      if (passwordInput) {
        passwordInput.value = "";
      }
      if (confirmPasswordInput) {
        confirmPasswordInput.value = "";
      }
      state.isAuthLoading = false;
      renderBoard();
    }
  }

  function switchAuthMode(mode) {
    state.authMode = mode;
    state.loginError = "";
    state.registerError = "";
    state.resetError = "";
    state.authSuccessMessage = "";
    renderAuthGate();
  }

  return {
    handleLogin,
    handleRegister,
    handleResetPassword,
    logoutAccount,
    restoreAccountSession,
    switchAuthMode,
  };
}
