import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
    const url = new URL(request.url);
    const authorizationId = url.searchParams.get("authorization_id");

    if (!authorizationId) {
        return NextResponse.json(
            { error: "Missing authorization_id" },
            { status: 400 },
        );
    }

    const cookieStore = await cookies();

    const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
        {
            cookies: {
                getAll() {
                    return cookieStore.getAll();
                },
                setAll(cookiesToSet) {
                    cookiesToSet.forEach(({ name, value, options }) => {
                        cookieStore.set(name, value, options);
                    });
                },
            },
        },
    );

    const { data: { session } } = await supabase.auth.getSession();

    if (!session) {
        const { error } = await supabase.auth.signInAnonymously();

        if (error) {
            return NextResponse.json(
                { error: error.message },
                { status: 500 },
            );
        }
    }

    return NextResponse.redirect(
        new URL(
            `/oauth/consent?authorization_id=${encodeURIComponent(authorizationId)}`,
            request.url,
        ),
    );
}