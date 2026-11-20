resp = client.chat.completions.create(
    model=model,
    temperature=0.1,
    messages=[
        {
            "role": "system",
            "content": (
                "Anda ialah penganalisis teknikal yang berdisiplin, objektif, "
                "dan ketat menapis setup dagangan tanpa rekaan."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}",
                        "detail": "high",
                    },
                },
            ],
        },
    ],
)
return resp.choices[0].message.content or ""
