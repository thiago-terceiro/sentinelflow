import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export default async function ConsentPage({
    searchParams,
}: {
    searchParams: Promise<{ authorization_id?: string }>;
}) {
    const { authorization_id } = await searchParams;

    if (!authorization_id) {
        return <div>Error: Missing authorization_id</div>;
    }

    const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
        {
            cookies: {
                getAll: async () => (await cookies()).getAll(),
                setAll: async (cookiesToSet) => {
                    const cookieStore = await cookies();
                    cookiesToSet.forEach(({ name, value, options }) =>
                        cookieStore.set(name, value, options)
                    );
                },
            },
        }
    );

    // Check if user is authenticated - commented out for demo purposes
    // const { data } = await supabase.auth.getClaims();
    // const claims = data?.claims;

    // if (!claims) {
    //     const redirectTo =
    //         `/oauth/consent?authorization_id=${encodeURIComponent(authorization_id)}`;

    //     // Redirect to login, preserving authorization_id
    //     redirect(`/auth/login?redirect=${encodeURIComponent(redirectTo)}`);
    // }

    // anonymous flow for demo testing
    const { data: claimsData } = await supabase.auth.getClaims();

    if (!claimsData?.claims) {
        const { error: anonymousError } =
            await supabase.auth.signInAnonymously();

        if (anonymousError) {
            return (
                <div>
                    Error creating demo session: {anonymousError.message}
                </div>
            );
        }
    }

    // Get authorization details using the authorization_id
    const { data: authDetails, error } = await supabase.auth.oauth.getAuthorizationDetails(authorization_id);

    if (error || !authDetails) {
        return <div>Error: {error?.message || "Invalid authorization request"}</div>;
    }

    // If no authorization_id returned, user has previously consented, redirect them
    if (!("authorization_id" in authDetails)) {
        redirect(authDetails.redirect_url);
    }

    return (
        <div style={{ maxWidth: "400px", margin: "4rem auto", padding: "2rem", fontFamily: "system-ui" }}>
            <h1>Authorize {authDetails.client.name}</h1>
            <p>This application wants to access your account.</p>

            <div style={{ margin: "1.5rem 0", padding: "1rem", background: "#f5f5f5", borderRadius: "8px" }}>
                <p><strong>Client:</strong> {authDetails.client.name}</p>
                <p><strong>Redirect URI:</strong> {authDetails.redirect_uri}</p>
                {authDetails.scope && authDetails.scope.trim() && (
                    <div>
                        <strong>Requested permissions:</strong>
                        <ul>
                            {authDetails.scope.split(" ").map((scopeItem) => (
                                <li key={scopeItem}>{scopeItem}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>

            <form action="/api/oauth/decision" method="POST">
                <input type="hidden" name="authorization_id" value={authorization_id} />
                <button
                    type="submit"
                    name="decision"
                    value="approve"
                    style={{
                        marginRight: "1rem",
                        padding: "0.75rem 1.5rem",
                        background: "#0070f3",
                        color: "white",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                    }}
                >
                    Approve
                </button>
                <button
                    type="submit"
                    name="decision"
                    value="deny"
                    style={{
                        padding: "0.75rem 1.5rem",
                        background: "transparent",
                        color: "#666",
                        border: "1px solid #ccc",
                        borderRadius: "4px",
                        cursor: "pointer",
                    }}
                >
                    Deny
                </button>
            </form>
        </div>
    );
}