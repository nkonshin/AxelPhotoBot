# OpenAI Images API - Документация

## Обзор

Images API предоставляет возможности для работы с изображениями через три основных эндпоинта:

- **Generations**: Генерация изображений с нуля на основе текстового промпта
- **Edits**: Редактирование существующих изображений с помощью нового промпта
- **Variations**: Генерация вариаций существующего изображения (только для DALL·E 2)

API поддерживает модели GPT Image (gpt-image-1.5, gpt-image-1, gpt-image-1-mini), а также DALL·E 2 и DALL·E 3.

---

## 1. Create Image (Генерация изображения)

### POST https://api.openai.com/v1/images/generations

Создает изображение на основе текстового промпта.

### Параметры запроса

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `prompt` | string | Да | Текстовое описание желаемого изображения. Максимальная длина: 32000 символов для GPT Image моделей, 1000 символов для dall-e-2, 4000 символов для dall-e-3 |
| `model` | string | Нет | Модель для генерации. Одна из: `dall-e-2`, `dall-e-3`, `gpt-image-1`, `gpt-image-1-mini`, `gpt-image-1.5`. По умолчанию: `dall-e-2` |
| `n` | integer | Нет | Количество генерируемых изображений. Должно быть от 1 до 10. По умолчанию: 1 |
| `size` | string | Нет | Размер изображений. Для GPT Image: `1024x1024`, `1536x1024` (ландшафт), `1024x1536` (портрет), или `auto` (по умолчанию). Для dall-e-2: `256x256`, `512x512`, `1024x1024`. Для dall-e-3: `1024x1024`, `1792x1024`, `1024x1792` |
| `quality` | string | Нет | Качество изображения. `auto` (по умолчанию), `high`, `medium`, `low`. Только для GPT Image моделей |
| `response_format` | string | Нет | Формат возврата. `url` или `b64_json`. URL действителен 60 минут. Для GPT Image моделей всегда возвращается base64. По умолчанию: `url` для DALL·E |
| `background` | string | Нет | Прозрачность фона: `transparent`, `opaque` или `auto` (по умолчанию). Только для GPT Image моделей. Требует формат `png` или `webp` |
| `output_format` | string | Нет | Формат изображения: `png`, `jpeg`, или `webp`. Только для GPT Image моделей. По умолчанию: `png` |
| `output_compression` | integer | Нет | Уровень сжатия (0-100%) для `webp` или `jpeg`. Только для GPT Image моделей. По умолчанию: 100 |
| `moderation` | string | Нет | Уровень модерации контента: `auto` (по умолчанию) или `strict`. Только для GPT Image моделей |
| `stream` | boolean | Нет | Включить потоковый режим. По умолчанию: `false`. Только для GPT Image моделей |
| `partial_images` | integer | Нет | Количество частичных изображений для потоковой генерации (0-3). Только для GPT Image моделей |
| `style` | string | Нет | Стиль изображений для dall-e-3: `vivid` (драматичный, гипер-реалистичный) или `natural` (более естественный) |
| `user` | string | Нет | Уникальный идентификатор пользователя для мониторинга и предотвращения злоупотреблений |

### Пример запроса (Python)

```python
import base64
from openai import OpenAI

client = OpenAI()

# Генерация изображения
response = client.images.generate(
    model="gpt-image-1.5",
    prompt="A cute baby sea otter",
    n=1,
    size="1024x1024"
)

# Декодирование и сохранение base64 изображения
image_bytes = base64.b64decode(response.data[0].b64_json)
with open("output.png", "wb") as f:
    f.write(image_bytes)
```

### Пример запроса (cURL)

```bash
curl https://api.openai.com/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-image-1.5",
    "prompt": "A cute baby sea otter",
    "n": 1,
    "size": "1024x1024"
  }'
```

### Пример с прозрачным фоном (Python)

```python
from openai import OpenAI
import base64

client = OpenAI()

response = client.images.generate(
    model="gpt-image-1.5",
    prompt="A red apple on a plate",
    background="transparent",
    output_format="png",
    size="1024x1024"
)

image_bytes = base64.b64decode(response.data[0].b64_json)
with open("apple_transparent.png", "wb") as f:
    f.write(image_bytes)
```

### Пример потоковой генерации (Python)

```python
from openai import OpenAI
import base64

client = OpenAI()

stream = client.images.generate(
    prompt="A gorgeous river made of white owl feathers through a winter landscape",
    model="gpt-image-1",
    stream=True,
    partial_images=2
)

for event in stream:
    if event.type == "image_generation.partial_image":
        idx = event.partial_image_index
        image_bytes = base64.b64decode(event.b64_json)
        with open(f"river_{idx}.png", "wb") as f:
            f.write(image_bytes)
```

### Ответ (Response Object)

```json
{
  "created": 1589478378,
  "data": [
    {
      "url": "https://...",
      "b64_json": "..."
    }
  ]
}
```

**Поля объекта:**
- `created` (integer): Unix timestamp создания
- `data` (array): Массив объектов изображений
  - `url` (string): URL изображения (действителен 60 минут)
  - `b64_json` (string): Base64-кодированные данные изображения
  - `revised_prompt` (string): Переработанный промпт (только для DALL·E 3)

---

## 2. Create Image Edit (Редактирование изображения)

### POST https://api.openai.com/v1/images/edits

Создает отредактированную или расширенную версию изображения на основе исходного изображения и промпта. Поддерживает только gpt-image-1 и dall-e-2.

### Параметры запроса

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `image` | file / array | Да | Изображение для редактирования. Для GPT Image: массив до 16 изображений (png/webp/jpg, <50MB каждое). Для dall-e-2: одно квадратное PNG изображение (<4MB) |
| `prompt` | string | Да | Описание желаемого изображения. Максимум: 32000 символов для GPT Image, 1000 для dall-e-2 |
| `mask` | file | Нет | Маска изображения (PNG с альфа-каналом). Прозрачные области (alpha=0) указывают, где нужно редактировать. Должна совпадать с размером изображения. Для dall-e-2: <4MB, квадратная |
| `model` | string | Нет | Модель для редактирования: `dall-e-2` или GPT Image модели. По умолчанию: `dall-e-2` |
| `n` | integer | Нет | Количество изображений для генерации (1-10). По умолчанию: 1 |
| `size` | string | Нет | Размер изображений. Для GPT Image: `1024x1024`, `1536x1024`, `1024x1536`, `auto`. Для dall-e-2: `256x256`, `512x512`, `1024x1024` |
| `quality` | string | Нет | Качество: `auto`, `high`, `medium`, `low`. Только для GPT Image |
| `background` | string | Нет | Прозрачность фона: `transparent`, `opaque`, `auto`. Только для GPT Image |
| `output_format` | string | Нет | Формат: `png`, `jpeg`, `webp`. Только для GPT Image |
| `output_compression` | integer | Нет | Сжатие (0-100%) для jpeg/webp. Только для GPT Image |
| `response_format` | string | Нет | `url` или `b64_json`. Для dall-e-2; GPT Image всегда возвращает base64 |
| `stream` | boolean | Нет | Потоковый режим. Только для GPT Image |
| `partial_images` | integer | Нет | Частичные изображения (0-3). Только для GPT Image |
| `user` | string | Нет | Идентификатор пользователя |

### Пример запроса с одним изображением (Python)

```python
from openai import OpenAI
import base64

client = OpenAI()

# Редактирование изображения
response = client.images.edit(
    model="dall-e-2",
    image=open("otter.png", "rb"),
    mask=open("mask.png", "rb"),
    prompt="A cute baby sea otter wearing a beret",
    n=1,
    size="1024x1024"
)

# Сохранение результата
if response.data[0].url:
    # Если URL
    print(f"Image URL: {response.data[0].url}")
else:
    # Если base64
    image_bytes = base64.b64decode(response.data[0].b64_json)
    with open("edited_otter.png", "wb") as f:
        f.write(image_bytes)
```

### Пример с несколькими изображениями (GPT Image) (Python)

```python
from openai import OpenAI
import base64

client = OpenAI()

prompt = """
Generate a photorealistic image of a gift basket on a white background 
labeled 'Relax & Unwind' with a ribbon and handwriting-like font, 
containing all the items in the reference pictures.
"""

response = client.images.edit(
    model="gpt-image-1",
    image=[
        open("body-lotion.png", "rb"),
        open("bath-bomb.png", "rb"),
        open("incense-kit.png", "rb"),
        open("soap.png", "rb")
    ],
    prompt=prompt
)

image_bytes = base64.b64decode(response.data[0].b64_json)
with open("gift_basket.png", "wb") as f:
    f.write(image_bytes)
```

### Пример запроса (cURL)

```bash
curl https://api.openai.com/v1/images/edits \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F image="@otter.png" \
  -F mask="@mask.png" \
  -F prompt="A cute baby sea otter wearing a beret" \
  -F n=2 \
  -F size="1024x1024"
```

### Создание маски программно (Python)

```python
from PIL import Image

# Создание маски 1024x1024 где нижняя половина прозрачна
width = 1024
height = 1024
mask = Image.new("RGBA", (width, height), (0, 0, 0, 255))

# Делаем нижнюю половину прозрачной
for x in range(width):
    for y in range(height // 2, height):
        mask.putpixel((x, y), (0, 0, 0, 0))  # alpha = 0

mask.save("mask.png")
```

### Преобразование черно-белого изображения в маску с альфа-каналом (Python)

```python
from PIL import Image
from io import BytesIO

# Загрузить черно-белую маску
mask = Image.open("bw_mask.png").convert("L")

# Преобразовать в RGBA
mask_rgba = mask.convert("RGBA")

# Использовать значения яркости как альфа-канал
mask_rgba.putalpha(mask)

# Преобразовать в байты для API
buf = BytesIO()
mask_rgba.save(buf, format="PNG")
mask_bytes = buf.getvalue()
```

### Ответ (Response Object)

```json
{
  "created": 1589478378,
  "data": [
    {
      "url": "https://...",
      "b64_json": "..."
    }
  ]
}
```

---

## 3. Create Image Variation (Создание вариаций)

### POST https://api.openai.com/v1/images/variations

Создает вариацию существующего изображения. Поддерживает только DALL·E 2.

### Параметры запроса

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `image` | file | Да | Изображение для создания вариаций. Должно быть квадратным PNG файлом, менее 4MB |
| `model` | string | Нет | Модель для вариаций. Только `dall-e-2` поддерживается |
| `n` | integer | Нет | Количество вариаций (1-10). По умолчанию: 1 |
| `size` | string | Нет | Размер: `256x256`, `512x512`, или `1024x1024`. По умолчанию: `1024x1024` |
| `response_format` | string | Нет | `url` или `b64_json`. По умолчанию: `url` |
| `user` | string | Нет | Идентификатор пользователя |

### Пример запроса (Python)

```python
from openai import OpenAI
import requests

client = OpenAI()

# Создание вариаций
response = client.images.create_variation(
    image=open("otter.png", "rb"),
    n=3,
    size="1024x1024"
)

# Скачивание и сохранение изображений
for i, img_data in enumerate(response.data):
    img_url = img_data.url
    img_content = requests.get(img_url).content
    
    with open(f"variation_{i}.png", "wb") as f:
        f.write(img_content)
```

### Пример с форматом base64 (Python)

```python
from openai import OpenAI
import base64

client = OpenAI()

response = client.images.create_variation(
    image=open("otter.png", "rb"),
    n=2,
    size="512x512",
    response_format="b64_json"
)

for i, img_data in enumerate(response.data):
    image_bytes = base64.b64decode(img_data.b64_json)
    with open(f"variation_{i}.png", "wb") as f:
        f.write(image_bytes)
```

### Пример запроса (cURL)

```bash
curl https://api.openai.com/v1/images/variations \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F image="@otter.png" \
  -F n=2 \
  -F size="1024x1024"
```

### Ответ (Response Object)

```json
{
  "created": 1589478378,
  "data": [
    {
      "url": "https://..."
    },
    {
      "url": "https://..."
    }
  ]
}
```

---

## 4. Image Object (Объект изображения)

### Структура объекта

Представляет сгенерированное изображение.

```json
{
  "b64_json": "iVBORw0KGgoAAAANSUhEUgAA...",
  "url": "https://oaidalleapiprodscus.blob.core.windows.net/...",
  "revised_prompt": "A cute baby sea otter floating on its back in calm blue water..."
}
```

### Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `b64_json` | string | Base64-кодированное изображение в формате JSON (если указан `response_format: "b64_json"`) |
| `url` | string | URL сгенерированного изображения (если указан `response_format: "url"`). Действителен 60 минут |
| `revised_prompt` | string | Переработанный промпт, использованный моделью для генерации (только для DALL·E 3) |

### Использование base64 изображений

```python
import base64
from PIL import Image
from io import BytesIO

# Декодирование base64
image_data = base64.b64decode(b64_json_string)

# Сохранение в файл
with open("image.png", "wb") as f:
    f.write(image_data)

# Или открытие с помощью PIL
image = Image.open(BytesIO(image_data))
image.show()
```

### Отображение base64 в HTML

```html
<img src="data:image/png;base64,iVBORw0KGgo..." alt="Generated image">
```

---

## Дополнительные примеры

### Полный рабочий пример с обработкой ошибок (Python)

```python
from openai import OpenAI
import base64
import os

# Инициализация клиента
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def generate_image(prompt, output_file="generated_image.png"):
    """
    Генерирует изображение и сохраняет его в файл
    """
    try:
        response = client.images.generate(
            model="gpt-image-1.5",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="high"
        )
        
        # Декодирование и сохранение
        image_bytes = base64.b64decode(response.data[0].b64_json)
        with open(output_file, "wb") as f:
            f.write(image_bytes)
        
        print(f"Изображение успешно сохранено в {output_file}")
        return output_file
        
    except Exception as e:
        print(f"Ошибка при генерации изображения: {e}")
        return None

# Использование
generate_image(
    prompt="A serene mountain landscape at sunset with a crystal clear lake",
    output_file="mountain_sunset.png"
)
```

### Редактирование с автоматической генерацией маски (Python)

```python
from openai import OpenAI
import base64

client = OpenAI()

# Шаг 1: Генерация маски с помощью API
mask_prompt = "generate a mask delimiting the character, white for character, black for background"

mask_response = client.images.edit(
    model="gpt-image-1",
    image=open("character.png", "rb"),
    prompt=mask_prompt
)

# Сохранение маски
mask_bytes = base64.b64decode(mask_response.data[0].b64_json)
with open("mask.png", "wb") as f:
    f.write(mask_bytes)

# Шаг 2: Использование маски для редактирования
edit_response = client.images.edit(
    model="gpt-image-1",
    image=open("character.png", "rb"),
    mask=open("mask.png", "rb"),
    prompt="Change the background to a futuristic cityscape"
)

# Сохранение результата
result_bytes = base64.b64decode(edit_response.data[0].b64_json)
with open("edited_character.png", "wb") as f:
    f.write(result_bytes)
```

### Batch генерация нескольких изображений (Python)

```python
from openai import OpenAI
import base64

client = OpenAI()

prompts = [
    "A red sports car on a mountain road",
    "A cozy coffee shop interior with warm lighting",
    "A futuristic robot in a neon city"
]

for i, prompt in enumerate(prompts):
    response = client.images.generate(
        model="gpt-image-1.5",
        prompt=prompt,
        n=1,
        size="1024x1024"
    )
    
    image_bytes = base64.b64decode(response.data[0].b64_json)
    with open(f"image_{i+1}.png", "wb") as f:
        f.write(image_bytes)
    
    print(f"Generated image {i+1}: {prompt}")
```

---

## Лучшие практики

### 1. Управление API ключами

```python
import os
from openai import OpenAI

# Рекомендуемый способ - через переменные окружения
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Никогда не храните ключи в коде!
# ❌ client = OpenAI(api_key="sk-...")
```

### 2. Обработка ошибок

```python
from openai import OpenAI, APIError, RateLimitError
import time

client = OpenAI()

def generate_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.images.generate(
                model="gpt-image-1.5",
                prompt=prompt,
                n=1,
                size="1024x1024"
            )
            return response
            
        except RateLimitError:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limit reached. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
                
        except APIError as e:
            print(f"API error: {e}")
            raise
```

### 3. Оптимизация стоимости

```python
# Используйте меньшие размеры для прототипов
response = client.images.generate(
    model="gpt-image-1-mini",  # Более дешевая модель
    prompt=prompt,
    size="1024x1024",  # Квадратные изображения быстрее
    quality="medium",   # Вместо "high"
    output_format="jpeg",  # Быстрее чем PNG
    output_compression=50  # Дополнительное сжатие
)
```

### 4. Работа с форматами

```python
import base64

# Для отображения в веб-приложении используйте base64
def image_to_data_url(response):
    b64_json = response.data[0].b64_json
    return f"data:image/png;base64,{b64_json}"

# Для сохранения на диск
def save_image(response, filename):
    image_bytes = base64.b64decode(response.data[0].b64_json)
    with open(filename, "wb") as f:
        f.write(image_bytes)
```

---

## Ограничения и замечания

### Ограничения моделей

- **DALL·E 2**: 
  - Размеры: 256x256, 512x512, 1024x1024
  - Только квадратные изображения для вариаций и редактирования
  - Максимум 4MB для загружаемых изображений

- **DALL·E 3**:
  - Размеры: 1024x1024, 1792x1024, 1024x1792
  - Не поддерживает вариации
  - Автоматически улучшает промпты

- **GPT Image модели**:
  - Размеры: 1024x1024, 1536x1024, 1024x1536, auto
  - До 16 входных изображений для редактирования
  - Максимум 50MB на изображение
  - Поддержка прозрачности
  - Стриминг и частичные изображения

### Время жизни URL

- URL изображений действительны только **60 минут** после генерации
- Для долгосрочного хранения используйте `response_format: "b64_json"` и сохраняйте файлы

### Расчет стоимости

Стоимость зависит от:
- Модели (gpt-image-1.5 > gpt-image-1 > gpt-image-1-mini)
- Размера изображения (больше токенов = выше стоимость)
- Качества (high > medium > low)
- Количества изображений (параметр `n`)

---

## Заключение

Images API предоставляет мощные возможности для работы с изображениями. Выбирайте подходящий эндпоинт в зависимости от задачи:

- **Generate** - для создания новых изображений с нуля
- **Edit** - для модификации существующих изображений
- **Variations** - для создания альтернативных версий (только DALL·E 2)

Используйте GPT Image модели для лучшего качества и расширенных возможностей, или DALL·E модели для простых задач и совместимости.