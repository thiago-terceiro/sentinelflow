export type TestAuthRole =
    | "investigator"
    | "senior_investigator"
    | "reviewer"
    | "auditor"
    | "admin";

type TestAuthUser = {
    role: TestAuthRole;
    username: string;
    password: string;
    token: string;
    label: string;
};

export const ACCESS_TOKEN_COOKIE_NAME =
    process.env.INTERNAL_ACCESS_TOKEN_COOKIE_NAME ?? "sentinelflow_access_token";
export const ID_TOKEN_COOKIE_NAME =
    process.env.INTERNAL_ID_TOKEN_COOKIE_NAME ?? "sentinelflow_id_token";
export const TEST_USER_COOKIE_NAME = "sentinelflow_test_user";
export const TEST_AUTH_SESSION_MAX_AGE_SECONDS = 60 * 60 * 12;

export const TEST_AUTH_USERS: readonly TestAuthUser[] = [
    {
        role: "investigator",
        username: "investigator",
        password: "investigator123",
        token: "dev-investigator",
        label: "Investigator",
    },
    {
        role: "senior_investigator",
        username: "senior",
        password: "senior123",
        token: "dev-senior",
        label: "Senior Investigator",
    },
    {
        role: "reviewer",
        username: "reviewer",
        password: "reviewer123",
        token: "dev-reviewer",
        label: "Reviewer",
    },
    {
        role: "auditor",
        username: "auditor",
        password: "auditor123",
        token: "dev-auditor",
        label: "Auditor",
    },
    {
        role: "admin",
        username: "admin",
        password: "admin123",
        token: "dev-admin",
        label: "Admin",
    },
];

export const sanitizeReturnPath = (path: string | null | undefined): string => {
    if (!path || !path.startsWith("/") || path.startsWith("//")) {
        return "/";
    }
    return path;
};

export const findTestAuthUser = (
    username: string,
    password: string,
    role: string,
): TestAuthUser | null => {
    const normalizedUsername = username.trim().toLowerCase();
    const normalizedRole = role.trim().toLowerCase();
    for (const user of TEST_AUTH_USERS) {
        if (
            user.role === normalizedRole
            && user.username === normalizedUsername
            && user.password === password
        ) {
            return user;
        }
    }
    return null;
};

export const cookieSecureFlag = (requestProtocol: string): boolean => {
    return requestProtocol === "https:";
};