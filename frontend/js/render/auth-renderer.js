import { state } from "../state/app-state.js";

export function renderAccountStatus({ onLogout }) {
  const accountStatus = document.querySelector("#account-status");
  if (!accountStatus) {
    return;
  }

  accountStatus.innerHTML = "";
  if (!state.isLoggedIn) {
    const badge = document.createElement("p");
    badge.className = "account-badge";
    badge.textContent = "Login required";
    accountStatus.append(badge);
    return;
  }

  const badge = document.createElement("p");
  badge.className = "account-badge";
  badge.textContent = `Logged in as: ${state.accountName}`;

  const logoutButton = document.createElement("button");
  logoutButton.type = "button";
  logoutButton.className = "button-secondary";
  logoutButton.textContent = "Logout";
  logoutButton.addEventListener("click", onLogout);

  accountStatus.append(badge, logoutButton);
}

export function renderAuthGate({
  onLogin,
  onRegister,
  onResetPassword,
  onSwitchAuthMode,
}) {
  const root = document.querySelector("#auth-root");
  const boardShell = document.querySelector(".board-shell");
  if (!root) {
    return;
  }

  if (boardShell) {
    boardShell.classList.toggle("board-locked", !state.isLoggedIn);
    boardShell.setAttribute("aria-hidden", state.isLoggedIn ? "false" : "true");
  }

  root.innerHTML = "";
  if (state.isLoggedIn) {
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop auth-backdrop";

  const modal = document.createElement("section");
  modal.className = "order-detail-modal auth-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "auth-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Operator login";

  const title = document.createElement("h2");
  title.id = "auth-title";
  title.textContent =
    state.authMode === "register"
      ? "Create operator account"
      : state.authMode === "reset"
      ? "Reset operator password"
      : "Login to Manual Dispatch Board";

  const note = document.createElement("p");
  note.className = "auth-note";
  note.textContent =
    "Use an operator account name and password. Passwords are not stored in plain text.";

  const form = document.createElement("form");
  form.className = "auth-form";
  const submitHandler =
    state.authMode === "register"
      ? onRegister
      : state.authMode === "reset"
      ? onResetPassword
      : onLogin;
  form.addEventListener("submit", submitHandler);

  form.append(
    createAuthInput("Account Name / Username", "account_name", {
      autocomplete: "username",
      minlength: 2,
      maxlength: 50,
      required: true,
    }),
  );

  if (state.authMode === "reset") {
    form.append(
      createAuthInput("Admin Reset Code", "admin_reset_code", {
        type: "password",
        autocomplete: "off",
        required: true,
      }),
      createAuthInput("New Password", "new_password", {
        type: "password",
        autocomplete: "new-password",
        minlength: 6,
        required: true,
      }),
      createAuthInput("Confirm New Password", "confirm_password", {
        type: "password",
        autocomplete: "new-password",
        minlength: 6,
        required: true,
      }),
    );
  } else {
    form.append(
      createAuthInput("Password", "password", {
        type: "password",
        autocomplete: state.authMode === "register" ? "new-password" : "current-password",
        minlength: 6,
        required: true,
      }),
    );
  }

  if (state.authMode === "register") {
    form.append(
      createAuthInput("Confirm Password", "confirm_password", {
        type: "password",
        autocomplete: "new-password",
        minlength: 6,
        required: true,
      }),
    );
  }

  const error = document.createElement("p");
  error.className = "board-error";
  const errorMessage =
    state.authMode === "register"
      ? state.registerError
      : state.authMode === "reset"
      ? state.resetError
      : state.loginError;
  error.hidden = !errorMessage;
  error.textContent = errorMessage;

  const success = document.createElement("p");
  success.className = "board-status";
  success.hidden = !state.authSuccessMessage;
  success.textContent = state.authSuccessMessage;

  const actions = document.createElement("div");
  actions.className = "form-actions auth-actions";

  if (state.authMode === "login") {
    const forgotButton = document.createElement("button");
    forgotButton.type = "button";
    forgotButton.className = "button-link";
    forgotButton.disabled = state.isAuthLoading;
    forgotButton.textContent = "Forgot password?";
    forgotButton.addEventListener("click", () => {
      onSwitchAuthMode("reset");
    });
    form.append(forgotButton);
  }

  const switchButton = document.createElement("button");
  switchButton.type = "button";
  switchButton.className = "button-secondary";
  switchButton.disabled = state.isAuthLoading;
  switchButton.textContent =
    state.authMode === "login" ? "Create account" : "Back to login";
  switchButton.addEventListener("click", () => {
    onSwitchAuthMode(state.authMode === "login" ? "register" : "login");
  });

  const submitButton = document.createElement("button");
  submitButton.type = "submit";
  submitButton.disabled = state.isAuthLoading;
  submitButton.textContent =
    state.authMode === "register"
      ? state.isAuthLoading
        ? "Creating..."
        : "Create account"
      : state.authMode === "reset"
      ? state.isAuthLoading
        ? "Resetting..."
        : "Reset password"
      : state.isAuthLoading
      ? "Logging in..."
      : "Login";

  actions.append(switchButton, submitButton);
  form.append(error, success, actions);
  modal.append(kicker, title, note, form);
  backdrop.append(modal);
  root.append(backdrop);
}

function createAuthInput(label, name, options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = label;

  const input = document.createElement("input");
  input.name = name;
  input.type = options.type || "text";
  input.required = Boolean(options.required);
  input.disabled = state.isAuthLoading;
  if (options.minlength) {
    input.minLength = options.minlength;
  }
  if (options.maxlength) {
    input.maxLength = options.maxlength;
  }
  if (options.autocomplete) {
    input.autocomplete = options.autocomplete;
  }

  wrapper.append(input);
  return wrapper;
}
