import tornado.web
import tornado.gen

from common.web import requestsManager

class handler(requestsManager.asyncRequestHandler):
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		self.set_status(200)
		self.write('{"code": 200, "clients": []}')
