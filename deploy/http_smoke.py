"""DOC: security#verification"""
import argparse
import html
import json
import re
import socket
import uuid
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--staging-copy', action='store_true', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    results = []
    with httpx.Client(base_url='http://127.0.0.1:8082', trust_env=False, timeout=15) as client:
        def check(name, condition):
            assert condition, name
            results.append(name)

        def get(path):
            response = client.get(path)
            check('GET '+path.split('?')[0], response.status_code == 200)
            return response

        def post(path, data=None, status=302):
            client.get('/shopping/')
            response = client.post(path, data=data or {}, headers={'X-CSRFToken': client.cookies['csrftoken']})
            check('POST '+path, response.status_code == status)
            return response

        initial = get('/shopping/')
        check('staging cookies', 'Secure' not in initial.headers.get('set-cookie', ''))
        check('CSRF enforced', client.post('/shopping/', data={'content': 'must fail'}).status_code == 403)
        check('PUT rejected', client.put('/shopping/', content=b'{}').status_code == 405)
        check('body cap', client.post('/shopping/', content=b'x'*262145).status_code == 413)
        check('host rejected', client.get('/', headers={'Host': 'attacker.invalid'}).status_code == 400)
        check('no inline scripts', "'unsafe-inline'" not in initial.headers['content-security-policy'])
        check('admin removed', client.get('/admin/').status_code == 404)
        marker = 'DEN TEST '+uuid.uuid4().hex[:8]
        attack = marker+' <img src=x onerror=alert(1)>; DROP TABLE myapp_item;--'
        post('/shopping/', {'content': attack})
        shopping = get('/shopping/').text
        check('hostile text escaped', html.escape(attack) in shopping and '<img src=x' not in shopping)
        item_id = re.search(r'data-item-id="(\d+)">\s*<span>'+re.escape(html.escape(attack)), shopping).group(1)
        post('/shopping/delete/'+item_id+'/')

        recipes_before = set(re.findall(r'/recipes/(\d+)/edit/', get('/recipes/').text))
        recipe = {'name': marker+' Soup', 'protein_type': 'veggie', 'frequency': '1', 'ingredients_text': 'onion\ncafé'}
        post('/recipes/add/', recipe)
        recipe_id, = set(re.findall(r'/recipes/(\d+)/edit/', get('/recipes/').text)) - recipes_before
        recipe['name'] = marker+' Edited'
        post('/recipes/'+recipe_id+'/edit/', recipe)
        check('recipe edited', recipe['name'] in get('/recipes/').text)
        post('/planner/regenerate/', {'start_date': '2099-04-01', 'num_days': '7'})
        post('/planner/swap/', {'date': '2099-04-01', 'recipe_id': recipe_id})
        check('manual meal visible', recipe['name'] in get('/planner/?year=2099&month=4').text)
        post('/planner/skip/', {'date': '2099-04-02'})
        post('/planner/add-to-shopping/', {'start_date': '2099-04-01', 'end_date': '2099-04-01'})
        check('ingredients transferred', 'café ('+recipe['name']+')' in get('/shopping/').text)
        post('/planner/skip/', {'date': 'not-a-date'}, status=400)
        post('/recipes/'+recipe_id+'/delete/')

        projects_before = set(re.findall(r'/projects/(\d+)/edit/', get('/projects/?status=all').text))
        project = {'name': marker, 'description': attack, 'project_type': 'other', 'urgency': '2'}
        post('/projects/', project)
        project_id, = set(re.findall(r'/projects/(\d+)/edit/', get('/projects/?status=all').text)) - projects_before
        project['name'] += ' Edited'
        post('/projects/'+project_id+'/edit/', project)
        check('project edited and escaped', html.escape(attack) in get('/projects/').text)
        post('/projects/'+project_id+'/completion/', {'is_completed': 'true'})
        check('completed project visible', project['name'] in get('/projects/?status=completed').text)
        post('/projects/'+project_id+'/completion/', {'is_completed': 'false'})
        post('/projects/'+project_id+'/delete/')

        plain = get('/shopping/download/')
        fallback = post('/shopping/smart-export/', status=200)
        check('AI disabled plain fallback', fallback.content == plain.content)
        download = post('/shopping/download-and-clear/', status=200)
        check('download matches cleared snapshot', download.content == plain.content)
        check('download attachment', 'attachment;' in download.headers['content-disposition'])
        check('cleared list', 'Your shopping list is empty.' in get('/shopping/').text)
        post('/shopping/', {'content': marker})
        post('/shopping/clear/')

    with socket.create_connection(('127.0.0.1', 8082), timeout=5) as connection:
        connection.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nX-Test: '+b'x'*17000+b'\r\n\r\n')
        check('Waitress header cap', b' 431 ' in connection.recv(4096).split(b'\r\n')[0])
    Path(args.output).write_text(json.dumps({'passed': True, 'checks': results}, indent=2)+'\n')
    print(json.dumps({'passed': True, 'checks': len(results)}))


if __name__ == '__main__':
    main()
