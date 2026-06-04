export type Result<T, E> = { ok: true; value: T } | { ok: false; error: E }

export async function request(path: string): Promise<Result<string, Error>> {
  try {
    const response = await fetch(`${process.env.API_BASE_URL}${path}`)
    return { ok: true, value: await response.text() }
  } catch (error) {
    return { ok: false, error: error as Error }
  }
}
