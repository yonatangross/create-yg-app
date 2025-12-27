import ky from 'ky';

export const api = ky.create({
  prefixUrl: '/api/v1',
  timeout: 60000,
  hooks: {
    beforeError: [
      async (error) => {
        const { response } = error;
        if (response) {
          try {
            const body = await response.json();
            error.message = body.error?.message || error.message;
          } catch {
            // Ignore JSON parse errors
          }
        }
        return error;
      },
    ],
  },
});
