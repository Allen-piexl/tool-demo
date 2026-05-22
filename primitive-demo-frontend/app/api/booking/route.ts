import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    const primitiveURL = process.env.BOOKING_PRIMITIVE_URL;

    if (!primitiveURL) {
      return NextResponse.json(
        {
          error: 'BOOKING_PRIMITIVE_URL is missing'
        },
        { status: 500 }
      );
    }

    const action = String(body.action || 'invoke');
    let path = '/invoke';
    let payload: Record<string, any> = {};

    if (action === 'invoke') {
      payload = {
        query: body.query,
        history: Array.isArray(body.history) ? body.history : []
      };
    } else if (action === 'open_session') {
      path = '/sessions/open';
      payload = {
        booking_url: body.booking_url,
        headless: body.headless !== false
      };
    } else if (action === 'session_message') {
      if (!body.session_id) {
        return NextResponse.json({ error: 'session_id is missing' }, { status: 400 });
      }
      path = `/sessions/${encodeURIComponent(String(body.session_id))}/message`;
      payload = {
        message: body.message || '',
        collected: body.collected || {}
      };
    } else if (action === 'continue_session') {
      if (!body.session_id) {
        return NextResponse.json({ error: 'session_id is missing' }, { status: 400 });
      }
      path = `/sessions/${encodeURIComponent(String(body.session_id))}/continue`;
      payload = {};
    } else {
      return NextResponse.json({ error: `Unknown booking action: ${action}` }, { status: 400 });
    }

    const response = await fetch(`${primitiveURL}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();
    if (data?.status?.screenshot_url && String(data.status.screenshot_url).startsWith('/')) {
      data.status.screenshot_url = `${primitiveURL}${data.status.screenshot_url}`;
    }
    if (data?.question?.status?.screenshot_url && String(data.question.status.screenshot_url).startsWith('/')) {
      data.question.status.screenshot_url = `${primitiveURL}${data.question.status.screenshot_url}`;
    }

    return NextResponse.json(data, { status: response.status });
  } catch (e: any) {
    return NextResponse.json(
      {
        error: String(e.message || e)
      },
      { status: 500 }
    );
  }
}
